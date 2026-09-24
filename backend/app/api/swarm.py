from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..audit import audit_user
from ..db import get_db
from ..evals import start_eval
from ..metrics import agent_health, agent_metrics_7d
from ..models import (AgentDef, Case, EvalRun, EvalSuite, Finding, PlaygroundSession, Run, SkillOverride, Span,
                      Workflow)
from ..orchestrator import orchestrator
from ..security import Principal, require
from ..serializers import agent_out, iso, run_out, run_summary
from ..settings_store import get_section
from ..skills_loader import all_skills, builtin_skills, skill_meta
from ..standards import STANDARDS, STANDARDS_BY_ID, standard_ref
from ..swarm.factory import system_prompt
from ..swarm.mcp import wazuh
from ..swarm.tools import PLATFORM_TOOL_NAMES
from .common import not_found

router = APIRouter()


def _running_agents(db: Session) -> set[str]:
    return {a for (a,) in db.query(Span.agent_id).join(Run, Run.id == Span.run_id).filter(
        Run.status == "running", Span.kind == "agent").distinct().all() if a}


def _skills_index(db: Session) -> dict:
    return {sid: {"name": (s.metadata or {}).get("display_name", sid)} for sid, s in all_skills(db).items()}


# -- agents -------------------------------------------------------------------------
@router.get("/agents")
def list_agents(_: Principal = Depends(require("agents:read")), db: Session = Depends(get_db)):
    health = agent_health(db, _running_agents(db))
    model = get_section(db, "model")
    idx = _skills_index(db)
    rows = db.query(AgentDef).order_by(AgentDef.sort_order).all()
    return {"items": [agent_out(a, idx, health.get(a.id, {}), model) for a in rows], "total": len(rows)}


def _tool_access(name: str) -> str:
    if name in PLATFORM_TOOL_NAMES:
        return "platform"
    if name.startswith("wazuh_check_"):
        return "verify"
    return "read"


@router.get("/agents/{agent_id}")
def get_agent(agent_id: str, _: Principal = Depends(require("agents:read")), db: Session = Depends(get_db)):
    a = db.get(AgentDef, agent_id) or not_found("agent")
    health = agent_health(db, _running_agents(db))
    runs = (db.query(Run).join(Span, Span.run_id == Run.id).filter(Span.agent_id == agent_id, Span.kind == "agent")
            .order_by(Run.started_at.desc()).distinct().limit(15).all())
    return {
        **agent_out(a, _skills_index(db), health.get(a.id, {}), get_section(db, "model")),
        "responsibilities": a.responsibilities or [],
        "tools": [{"name": t, "source": "platform" if t in PLATFORM_TOOL_NAMES else "mcp", "access": _tool_access(t)}
                  for t in a.tools or []] + [{"name": "skills", "source": "platform", "access": "platform"}],
        "recent_runs": [run_summary(r) for r in runs],
        "metrics_7d": agent_metrics_7d(db, agent_id),
    }


class AgentPatch(BaseModel):
    enabled: bool | None = None
    model_override: dict | None = None
    clear_model_override: bool = False
    autonomy_cap: str | None = None
    skills: list[str] | None = None
    tools: list[str] | None = None
    temperature: float | None = None
    max_tokens: int | None = None
    system_prompt_extra: str | None = None


@router.patch("/agents/{agent_id}")
def update_agent(agent_id: str, body: AgentPatch, principal: Principal = Depends(require("agents:write")),
                 db: Session = Depends(get_db)):
    a = db.get(AgentDef, agent_id) or not_found("agent")
    data = body.model_dump(exclude_unset=True)
    if "model_override" in data or body.clear_model_override:
        mo = data.get("model_override")
        a.model_override = mo if mo and mo.get("provider") else None
    if body.autonomy_cap is not None:
        if body.autonomy_cap not in {"observe", "recommend", "supervised", "autonomous"}:
            raise HTTPException(400, "invalid autonomy_cap")
        a.autonomy_cap = body.autonomy_cap
    if body.skills is not None:
        known = set(all_skills(db))
        unknown = [s for s in body.skills if s not in known]
        if unknown:
            raise HTTPException(400, f"unknown skills: {', '.join(unknown)}")
        a.skills = body.skills
    for field in ("enabled", "tools", "temperature", "max_tokens", "system_prompt_extra"):
        if field in data:
            setattr(a, field, data[field])
    audit_user(db, principal, "agent.updated", agent_id, {k: v for k, v in data.items() if k != "system_prompt_extra"})
    db.commit()
    return get_agent(agent_id, principal, db)


@router.get("/agents/{agent_id}/prompt")
def agent_prompt(agent_id: str, _: Principal = Depends(require("runs:debug")), db: Session = Depends(get_db)):
    a = db.get(AgentDef, agent_id) or not_found("agent")
    org = get_section(db, "org").get("name", "the organization")
    skills = all_skills(db)
    mcp = {t.tool_name: t for t in wazuh.agent_tools(get_section(db, "wazuh"))}
    tools = []
    for name in a.tools or []:
        if name in mcp:
            tools.append({"name": name, "description": mcp[name].tool_spec.get("description", "")[:300], "source": "mcp"})
        else:
            tools.append({"name": name, "description": "", "source": "platform" if name in PLATFORM_TOOL_NAMES else "mcp (unavailable)"})
    return {"system_prompt": system_prompt(a, org, a.handoffs or [], "swarm"),
            "skills_injected": [{"id": s, "description": skills[s].description} for s in a.skills or [] if s in skills],
            "tools": tools}


@router.get("/agents/{agent_id}/health")
def agent_health_one(agent_id: str, _: Principal = Depends(require("agents:read")), db: Session = Depends(get_db)):
    db.get(AgentDef, agent_id) or not_found("agent")
    h = agent_health(db, _running_agents(db)).get(agent_id, {})
    return {k: v for k, v in h.items() if not k.startswith("_")}


# -- skills --------------------------------------------------------------------------
def _used_by(db: Session) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for a in db.query(AgentDef).all():
        for s in a.skills or []:
            out.setdefault(s, []).append(a.id)
    return out


@router.get("/skills")
def list_skills(category: str = "", _: Principal = Depends(require("skills:read")), db: Session = Depends(get_db)):
    used = _used_by(db)
    builtin = set(builtin_skills())
    overrides = {o.id: o for o in db.query(SkillOverride).all()}
    items = [skill_meta(s, builtin, used.get(sid, []), overrides[sid].updated_at if sid in overrides else None)
             for sid, s in sorted(all_skills(db).items())]
    if category:
        items = [i for i in items if i["category"] == category]
    return {"items": items, "total": len(items)}


@router.get("/skills/{skill_id}")
def get_skill(skill_id: str, _: Principal = Depends(require("skills:read")), db: Session = Depends(get_db)):
    skills = all_skills(db)
    s = skills.get(skill_id) or not_found("skill")
    o = db.get(SkillOverride, skill_id)
    return {**skill_meta(s, set(builtin_skills()), _used_by(db).get(skill_id, []), o.updated_at if o else None),
            "body_md": s.instructions}


class SkillIn(BaseModel):
    id: str | None = None
    name: str | None = None
    description: str | None = None
    category: str | None = None
    body_md: str | None = None
    standards: list[str] | None = None
    tools: list[str] | None = None


def _upsert_skill(db: Session, skill_id: str, body: SkillIn, principal: Principal, create: bool) -> dict:
    import re
    if not re.fullmatch(r"[a-z0-9]([a-z0-9-]*[a-z0-9])?", skill_id) or len(skill_id) > 64:
        raise HTTPException(400, "skill id must be lowercase letters, digits and hyphens")
    existing = all_skills(db).get(skill_id)
    if create and existing:
        raise HTTPException(409, "skill already exists")
    if not create and not existing:
        not_found("skill")
    md = (existing.metadata or {}) if existing else {}
    row = db.get(SkillOverride, skill_id) or SkillOverride(id=skill_id, builtin=skill_id in builtin_skills())
    row.name = body.name or md.get("display_name") or skill_id.replace("-", " ").title()
    row.description = body.description or (existing.description if existing else "")
    row.category = body.category or md.get("category", "general")
    row.standards = body.standards if body.standards is not None else md.get("standards", [])
    row.tools = body.tools if body.tools is not None else (existing.allowed_tools or [] if existing else [])
    row.body_md = body.body_md if body.body_md is not None else (existing.instructions if existing else "")
    if not row.description:
        raise HTTPException(400, "description is required")
    db.merge(row)
    audit_user(db, principal, "skill.created" if create else "skill.updated", skill_id)
    db.commit()
    return get_skill(skill_id, principal, db)


@router.post("/skills")
def create_skill(body: SkillIn, principal: Principal = Depends(require("skills:write")), db: Session = Depends(get_db)):
    if not body.id:
        raise HTTPException(400, "id is required")
    return _upsert_skill(db, body.id, body, principal, create=True)


@router.put("/skills/{skill_id}")
def update_skill(skill_id: str, body: SkillIn, principal: Principal = Depends(require("skills:write")),
                 db: Session = Depends(get_db)):
    return _upsert_skill(db, skill_id, body, principal, create=False)


# -- standards ------------------------------------------------------------------------
def _coverage(db: Session):
    agents = db.query(AgentDef).all()
    skills = all_skills(db)
    refs: dict[str, int] = {}
    for (sr,) in db.query(Finding.standard_refs).all():
        for r in sr or []:
            refs[r.upper()] = refs.get(r.upper(), 0) + 1
    return agents, skills, refs


def _std_summary(std: dict, agents, skills, refs) -> dict:
    a_ids = [a.id for a in agents if std["id"] in (a.standards or [])]
    s_ids = [sid for sid, s in skills.items() if std["id"] in ((s.metadata or {}).get("standards") or [])]
    covered = sum(1 for cid, _ in std["controls"] if a_ids or s_ids)
    return {"id": std["id"], "name": std["name"], "publisher": std["publisher"], "url": std["url"],
            "description": std["description"], "controls_mapped": len(std["controls"]),
            "coverage_pct": round(covered / len(std["controls"]) * 100) if std["controls"] else 0,
            "agents": a_ids, "skills": s_ids,
            "evidence_count": sum(n for r, n in refs.items() if std["name"].split()[0].upper() in r or std["id"].upper() in r)}


@router.get("/standards")
def list_standards(_: Principal = Depends(require("standards:read")), db: Session = Depends(get_db)):
    agents, skills, refs = _coverage(db)
    return [_std_summary(s, agents, skills, refs) for s in STANDARDS]


@router.get("/standards/{std_id}")
def get_standard(std_id: str, _: Principal = Depends(require("standards:read")), db: Session = Depends(get_db)):
    std = STANDARDS_BY_ID.get(std_id) or not_found("standard")
    agents, skills, refs = _coverage(db)
    summary = _std_summary(std, agents, skills, refs)
    covered_by = [{"type": "agent", "id": a} for a in summary["agents"]] + [{"type": "skill", "id": s} for s in summary["skills"]]
    return {**summary, "controls": [{"id": cid, "title": title, "covered_by": covered_by,
                                     "evidence_count": sum(n for r, n in refs.items() if cid.upper() in r)}
                                    for cid, title in std["controls"]]}


# -- workflows --------------------------------------------------------------------------
def _wf_out(db: Session, wf: Workflow) -> dict:
    from datetime import timedelta
    from ..db import utcnow
    rows = db.query(Run.status).filter(Run.workflow_id == wf.id, Run.started_at >= utcnow() - timedelta(days=7)).all()
    done = [r for (r,) in rows if r in {"completed", "failed"}]
    return {"id": wf.id, "name": wf.name, "description": wf.description, "mode": wf.mode, "enabled": wf.enabled,
            "trigger": wf.trigger, "entry_agent": wf.entry_agent, "steps": wf.steps, "last_run_at": iso(wf.last_run_at),
            "runs_7d": len(rows), "success_rate": round(sum(1 for r in done if r == "completed") / len(done), 3) if done else None}


@router.get("/workflows")
def list_workflows(_: Principal = Depends(require("workflows:read")), db: Session = Depends(get_db)):
    rows = db.query(Workflow).order_by(Workflow.sort_order).all()
    return {"items": [_wf_out(db, w) for w in rows], "total": len(rows)}


@router.get("/workflows/{wf_id}")
def get_workflow(wf_id: str, _: Principal = Depends(require("workflows:read")), db: Session = Depends(get_db)):
    return _wf_out(db, db.get(Workflow, wf_id) or not_found("workflow"))


class WorkflowPatch(BaseModel):
    name: str | None = None
    description: str | None = None
    enabled: bool | None = None
    trigger: dict | None = None
    steps: list[dict] | None = None
    mode: str | None = None
    entry_agent: str | None = None


@router.put("/workflows/{wf_id}")
def update_workflow(wf_id: str, body: WorkflowPatch, principal: Principal = Depends(require("workflows:write")),
                    db: Session = Depends(get_db)):
    wf = db.get(Workflow, wf_id) or not_found("workflow")
    data = body.model_dump(exclude_unset=True)
    if "mode" in data and data["mode"] not in {"swarm", "graph"}:
        raise HTTPException(400, "mode must be swarm or graph")
    if "steps" in data:
        known = {a for (a,) in db.query(AgentDef.id).all()}
        for s in data["steps"]:
            if s.get("agent_id") not in known:
                raise HTTPException(400, f"unknown agent {s.get('agent_id')}")
    for k, v in data.items():
        setattr(wf, k, v)
    audit_user(db, principal, "workflow.updated", wf_id, {k: v for k, v in data.items() if k != "steps"})
    db.commit()
    return _wf_out(db, wf)


class WorkflowRunIn(BaseModel):
    input: dict = {}
    dry_run: bool = False


@router.post("/workflows/{wf_id}/run")
def run_workflow(wf_id: str, body: WorkflowRunIn = WorkflowRunIn(), principal: Principal = Depends(require("workflows:run")),
                 db: Session = Depends(get_db)):
    wf = db.get(Workflow, wf_id) or not_found("workflow")
    if not wf.enabled:
        raise HTTPException(409, "workflow is disabled")
    audit_user(db, principal, "workflow.run", wf_id)
    db.commit()
    return orchestrator.start_run(wf_id, body.input, trigger="manual", dry_run=body.dry_run)


# -- runs -------------------------------------------------------------------------------
@router.get("/runs")
def list_runs(status: str = "", workflow_id: str = "", agent_id: str = "", case_id: str = "", trigger: str = "",
              limit: int = 50, offset: int = 0, _: Principal = Depends(require("runs:read")), db: Session = Depends(get_db)):
    q = db.query(Run, Case.number).outerjoin(Case, Case.id == Run.case_id).order_by(Run.started_at.desc())
    if status:
        q = q.filter(Run.status.in_(status.split(",")))
    if workflow_id:
        q = q.filter(Run.workflow_id == workflow_id)
    if case_id:
        q = q.filter(Run.case_id == case_id)
    if trigger:
        q = q.filter(Run.trigger == trigger)
    if agent_id:
        q = q.filter(Run.id.in_(db.query(Span.run_id).filter(Span.agent_id == agent_id, Span.kind == "agent")))
    total = q.order_by(None).count()
    rows = q.limit(max(1, min(limit, 500))).offset(offset).all()
    return {"items": [run_summary(r, n) for r, n in rows], "total": total}


@router.get("/runs/{run_id}")
def get_run(run_id: str, _: Principal = Depends(require("runs:read")), db: Session = Depends(get_db)):
    r = db.get(Run, run_id) or not_found("run")
    spans = db.query(Span).filter_by(run_id=run_id).order_by(Span.started_at).all()
    num = db.get(Case, r.case_id).number if r.case_id else None
    return run_out(r, spans, num)


@router.post("/runs/{run_id}/cancel")
def cancel_run(run_id: str, principal: Principal = Depends(require("workflows:run")), db: Session = Depends(get_db)):
    r = db.get(Run, run_id) or not_found("run")
    if r.status not in {"queued", "running"}:
        raise HTTPException(409, f"run is {r.status}")
    orchestrator.cancel(run_id)
    audit_user(db, principal, "run.cancelled", run_id)
    db.commit()
    return run_summary(r)


@router.post("/runs/{run_id}/replay")
def replay_run(run_id: str, principal: Principal = Depends(require("runs:debug")), db: Session = Depends(get_db)):
    r = db.get(Run, run_id) or not_found("run")
    audit_user(db, principal, "run.replayed", run_id)
    db.commit()
    if r.workflow_id:
        return orchestrator.start_run(r.workflow_id, r.input or {}, trigger="manual", case_id=r.case_id, dry_run=r.dry_run)
    inp = r.input or {}
    if inp.get("agent_id"):
        return orchestrator.run_agent(inp["agent_id"], inp.get("prompt", ""), dry_run=True)
    raise HTTPException(400, "this run cannot be replayed")


# -- playground ---------------------------------------------------------------------------
class SessionIn(BaseModel):
    agent_id: str
    dry_run: bool = True


@router.post("/playground/sessions")
def new_session(body: SessionIn, principal: Principal = Depends(require("playground:use")), db: Session = Depends(get_db)):
    db.get(AgentDef, body.agent_id) or not_found("agent")
    s = PlaygroundSession(agent_id=body.agent_id, user_id=principal.id, dry_run=body.dry_run, messages=[])
    db.add(s)
    db.commit()
    return {"session_id": s.id, "agent_id": s.agent_id, "dry_run": s.dry_run}


class MessageIn(BaseModel):
    content: str


@router.post("/playground/sessions/{sid}/messages")
def send_message(sid: str, body: MessageIn, principal: Principal = Depends(require("playground:use")),
                 db: Session = Depends(get_db)):
    s = db.get(PlaygroundSession, sid) or not_found("session")
    if s.user_id != principal.id:
        raise HTTPException(403, "not your session")
    if not s.dry_run and "workflows:run" not in principal.permissions:
        raise HTTPException(403, "live playground sessions require workflows:run")
    run = orchestrator.run_agent(s.agent_id, body.content, dry_run=s.dry_run, history=list(s.messages or []),
                                 session_id=s.id)
    return {"run_id": run["id"]}


def _flatten_messages(messages: list) -> list[dict]:
    out = []
    for m in messages or []:
        for b in m.get("content", []):
            if "text" in b and b["text"].strip():
                out.append({"role": m.get("role"), "content": b["text"]})
            elif "toolUse" in b:
                out.append({"role": "tool", "tool_name": b["toolUse"].get("name"), "content": b["toolUse"].get("input")})
            elif "toolResult" in b:
                text = " ".join(x.get("text", "") for x in b["toolResult"].get("content", []) if isinstance(x, dict))
                out.append({"role": "tool", "tool_name": "result", "content": text[:4000]})
    return out


@router.get("/playground/sessions/{sid}")
def get_session(sid: str, principal: Principal = Depends(require("playground:use")), db: Session = Depends(get_db)):
    s = db.get(PlaygroundSession, sid) or not_found("session")
    return {"session_id": s.id, "agent_id": s.agent_id, "dry_run": s.dry_run, "messages": _flatten_messages(s.messages)}


# -- evals ----------------------------------------------------------------------------------
def _suite_out(db: Session, s: EvalSuite, full: bool = False) -> dict:
    last = db.query(EvalRun).filter_by(suite_id=s.id, status="completed").order_by(EvalRun.started_at.desc()).first()
    out = {"id": s.id, "name": s.name, "agent_id": s.agent_id, "description": s.description, "cases": len(s.cases or []),
           "evaluators": s.evaluators or [], "last_score": last.overall_score if last else None,
           "last_run_at": iso(last.started_at) if last else None}
    if full:
        out["cases"] = s.cases
    return out


def _eval_run_out(r: EvalRun) -> dict:
    return {"id": r.id, "suite_id": r.suite_id, "status": r.status, "started_at": iso(r.started_at),
            "finished_at": iso(r.finished_at), "overall_score": r.overall_score, "pass_rate": r.pass_rate,
            "results": r.results or [], "error": r.error}


@router.get("/evals/suites")
def list_suites(_: Principal = Depends(require("evals:read")), db: Session = Depends(get_db)):
    return [_suite_out(db, s) for s in db.query(EvalSuite).all()]


@router.get("/evals/suites/{suite_id}")
def get_suite(suite_id: str, _: Principal = Depends(require("evals:read")), db: Session = Depends(get_db)):
    return _suite_out(db, db.get(EvalSuite, suite_id) or not_found("suite"), full=True)


@router.post("/evals/suites/{suite_id}/run")
def run_suite(suite_id: str, principal: Principal = Depends(require("evals:run")), db: Session = Depends(get_db)):
    db.get(EvalSuite, suite_id) or not_found("suite")
    audit_user(db, principal, "eval.run", suite_id)
    db.commit()
    rid = start_eval(suite_id)
    return _eval_run_out(db.get(EvalRun, rid))


@router.get("/evals/runs")
def list_eval_runs(suite_id: str = "", _: Principal = Depends(require("evals:read")), db: Session = Depends(get_db)):
    q = db.query(EvalRun).order_by(EvalRun.started_at.desc())
    if suite_id:
        q = q.filter_by(suite_id=suite_id)
    rows = q.limit(100).all()
    return {"items": [_eval_run_out(r) for r in rows], "total": len(rows)}


@router.get("/evals/runs/{run_id}")
def get_eval_run(run_id: str, _: Principal = Depends(require("evals:read")), db: Session = Depends(get_db)):
    return _eval_run_out(db.get(EvalRun, run_id) or not_found("eval run"))
