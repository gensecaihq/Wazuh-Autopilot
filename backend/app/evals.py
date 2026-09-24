"""Agent evaluation with strands-agents-evals.

Each suite case runs the agent in dry-run mode (no state changes) and scores it
with deterministic evaluators: ToolCalled for every expected tool and Contains
for every expected string (matched against the agent's transcript: its messages
and tool arguments).
"""

import json
import logging
from concurrent.futures import ThreadPoolExecutor

from strands.hooks import BeforeToolCallEvent, HookProvider, HookRegistry
from strands_evals import Case as EvalCase
from strands_evals import Experiment
from strands_evals.evaluators import Contains, ToolCalled

from .db import session_scope, utcnow
from .models import AgentDef, EvalRun, EvalSuite, Run, Span
from .settings_store import get_section
from .skills_loader import all_skills
from .swarm.factory import build_agent
from .swarm.mcp import wazuh
from .swarm.telemetry import RunTracer
from .swarm.tools import RunContext, build_platform_tools

log = logging.getLogger(__name__)
_pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="evals")


class _ToolRecorder(HookProvider):
    def __init__(self) -> None:
        self.calls: list[str] = []
        self.inputs: list[str] = []

    def register_hooks(self, registry: HookRegistry) -> None:
        registry.add_callback(BeforeToolCallEvent, self._record)

    def _record(self, event: BeforeToolCallEvent) -> None:
        self.calls.append(event.tool_use.get("name", ""))
        self.inputs.append(json.dumps(event.tool_use.get("input", {}), default=str))


def start_eval(suite_id: str) -> str:
    with session_scope() as db:
        if not db.get(EvalSuite, suite_id):
            raise ValueError(f"suite {suite_id} not found")
        run = EvalRun(suite_id=suite_id, status="running")
        db.add(run)
        db.flush()
        run_id = run.id
    _pool.submit(_execute, run_id, suite_id)
    return run_id


def _execute(eval_run_id: str, suite_id: str) -> None:
    try:
        with session_scope() as db:
            suite = db.get(EvalSuite, suite_id)
            agent_def = db.get(AgentDef, suite.agent_id)
            cases = list(suite.cases or [])
            model_settings = get_section(db, "model")
            wazuh_settings = get_section(db, "wazuh")
            org = get_section(db, "org").get("name", "Acme")
            skills = all_skills(db)
            trace_run = Run(workflow_id=None, workflow_name=f"Eval: {suite.name}", mode="single", status="running",
                            trigger="eval", dry_run=True, input={"suite_id": suite_id})
            db.add(trace_run)
            db.flush()
            root = Span(run_id=trace_run.id, kind="run", name=f"Eval: {suite.name}")
            db.add(root)
            db.flush()
            trace_run_id, root_id = trace_run.id, root.id
        mcp_tools = wazuh.agent_tools(wazuh_settings)
        tracer = RunTracer(trace_run_id, root_id, (float(model_settings.get("price_in_per_mtok") or 0),
                                                   float(model_settings.get("price_out_per_mtok") or 0)))
        results = []
        for c in cases:
            recorder = _ToolRecorder()

            def task(case: EvalCase, recorder=recorder):
                ctx = RunContext(run_id=trace_run_id, dry_run=True)
                agent = build_agent(agent_def, model_settings=model_settings, org_name=org, mcp_tools=mcp_tools,
                                    platform_tools=build_platform_tools(ctx), skills=skills, tracer=tracer,
                                    mode="single", handoff_targets=[], extra_hooks=[recorder])
                out = str(agent(case.input))
                transcript = out + "\n" + "\n".join(recorder.inputs)
                return {"output": transcript, "trajectory": list(recorder.calls)}

            evaluators = [ToolCalled(t) for t in c.get("expected_tools", [])]
            evaluators += [Contains(v, case_sensitive=False) for v in c.get("expected_contains", [])]
            exp = Experiment(cases=[EvalCase(name=c["name"], input=c["input"])], evaluators=evaluators)
            report = exp.run_evaluations(task)
            per_eval = {}
            for row, score, passed in zip(report.cases, report.scores, report.test_passes):
                per_eval[row.get("evaluator", "evaluator")] = score
            passed = all(report.test_passes) if report.test_passes else False
            results.append({"case": c["name"], "passed": passed, "score": round(report.overall_score, 3),
                            "evaluator_scores": per_eval, "reason": "; ".join(r for r in report.reasons if r)[:1000],
                            "tools_called": recorder.calls, "output_preview": ""})
        with session_scope() as db:
            er = db.get(EvalRun, eval_run_id)
            er.status = "completed"
            er.finished_at = utcnow()
            er.results = results
            er.overall_score = round(sum(r["score"] for r in results) / len(results), 3) if results else 0.0
            er.pass_rate = round(sum(1 for r in results if r["passed"]) / len(results), 3) if results else 0.0
        tracer.flush_totals()
        with session_scope() as db:
            tr = db.get(Run, trace_run_id)
            tr.status, tr.finished_at = "completed", utcnow()
            tr.duration_ms = int((tr.finished_at - tr.started_at).total_seconds() * 1000)
    except Exception as e:
        log.exception("eval run failed")
        with session_scope() as db:
            er = db.get(EvalRun, eval_run_id)
            er.status, er.error, er.finished_at = "failed", f"{type(e).__name__}: {e}", utcnow()
