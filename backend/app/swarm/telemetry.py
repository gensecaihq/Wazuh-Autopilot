"""Run tracing: Strands hooks → spans in the database + live SSE events.

Complements (does not replace) Strands' native OpenTelemetry export, which is
enabled separately when an OTLP endpoint is configured.
"""

import json
import threading
import time
from datetime import datetime, timezone

from strands.hooks import (AfterInvocationEvent, AfterModelCallEvent, AfterToolCallEvent, BeforeInvocationEvent,
                           BeforeModelCallEvent, BeforeToolCallEvent, HookProvider, HookRegistry)

from ..db import session_scope
from ..events import bus
from ..models import Run, Span, new_id
from ..serializers import span_out
from .mcp import is_action_tool

PREVIEW = 2000


def _preview(value) -> str:
    if value is None:
        return ""
    if not isinstance(value, str):
        try:
            value = json.dumps(value, default=str)
        except Exception:
            value = str(value)
    return value[:PREVIEW]


def _tool_result_text(result) -> str:
    if not isinstance(result, dict):
        return _preview(result)
    parts = []
    for block in result.get("content") or []:
        if isinstance(block, dict):
            parts.append(block.get("text") or json.dumps(block.get("json", ""), default=str))
    return _preview("\n".join(parts))


class RunTracer(HookProvider):
    """One tracer per run, shared by every agent in the run."""

    def __init__(self, run_id: str, root_span_id: str, prices: tuple[float, float]):
        self.run_id = run_id
        self.root = root_span_id
        self.price_in, self.price_out = prices
        self._lock = threading.Lock()
        self._open: dict[str, dict] = {}
        self._agent_span: dict[str, str] = {}
        self._usage_seen: dict[str, tuple[int, int]] = {}
        self._last_model_span: dict[str, str] = {}
        self.tokens_in = self.tokens_out = self.tool_calls = self.errors = 0
        self.agents: list[str] = []
        self.handoffs: list[dict] = []
        self.last_text: dict[str, str] = {}
        self._agent_tokens: dict[str, list[int]] = {}

    # -- span helpers -------------------------------------------------------
    def _start(self, key: str, kind: str, name: str, agent: str | None, parent: str | None, inp="", attrs=None) -> str:
        sid = new_id("spn")
        self._open[key] = {"id": sid, "t0": time.time(), "started": datetime.now(timezone.utc), "kind": kind,
                           "name": name, "agent": agent, "parent": parent, "input": _preview(inp),
                           "attrs": attrs or {}}
        return sid

    def _end(self, key: str, status="ok", output="", error=None, tokens=(0, 0), attrs=None) -> None:
        s = self._open.pop(key, None)
        if not s:
            return
        span = Span(id=s["id"], run_id=self.run_id, parent_id=s["parent"], kind=s["kind"], name=s["name"],
                    agent_id=s["agent"], status=status, started_at=s["started"],
                    duration_ms=int((time.time() - s["t0"]) * 1000), tokens_in=tokens[0], tokens_out=tokens[1],
                    attributes={**s["attrs"], **(attrs or {})}, input_preview=s["input"],
                    output_preview=_preview(output), error=error)
        with session_scope() as db:
            db.add(span)
        out = span_out(span)
        if span.kind == "handoff":
            try:
                inp = json.loads(s["input"]) if s["input"] else {}
            except ValueError:
                inp = {}
            out["from"], out["to"] = span.agent_id, inp.get("agent_name")
        bus.publish("run.step", {**out, "run_id": self.run_id, "span_id": span.id, "span": out})

    def instant(self, kind: str, name: str, agent: str | None, attrs=None, status="ok", output="") -> None:
        with self._lock:
            key = new_id("k")
            self._start(key, kind, name, agent, self._agent_span.get(agent or "", self.root), attrs=attrs)
            self._end(key, status=status, output=output)

    def _settle_usage(self, agent_obj) -> None:
        """Strands updates token usage after AfterModelCallEvent, so attribute each model call's tokens at the
        next checkpoint (next model call or end of invocation) and patch the span retroactively."""
        agent = agent_obj.name
        u = agent_obj.event_loop_metrics.accumulated_usage
        cur = (u.get("inputTokens", 0), u.get("outputTokens", 0))
        seen = self._usage_seen.get(agent, (0, 0))
        d_in, d_out = max(0, cur[0] - seen[0]), max(0, cur[1] - seen[1])
        self._usage_seen[agent] = cur
        span_id = self._last_model_span.pop(agent, None)
        if not (d_in or d_out):
            return
        self.tokens_in += d_in
        self.tokens_out += d_out
        if span_id:
            with session_scope() as db:
                row = db.get(Span, span_id)
                if row:
                    row.tokens_in, row.tokens_out = d_in, d_out
        agent_span = self._agent_tokens.setdefault(agent, [0, 0])
        agent_span[0] += d_in
        agent_span[1] += d_out

    # -- hooks --------------------------------------------------------------
    def register_hooks(self, registry: HookRegistry) -> None:
        registry.add_callback(BeforeInvocationEvent, self._before_invocation)
        registry.add_callback(AfterInvocationEvent, self._after_invocation)
        registry.add_callback(BeforeModelCallEvent, self._before_model)
        registry.add_callback(AfterModelCallEvent, self._after_model)
        registry.add_callback(BeforeToolCallEvent, self._before_tool)
        registry.add_callback(AfterToolCallEvent, self._after_tool)

    def _before_invocation(self, event: BeforeInvocationEvent) -> None:
        agent = event.agent.name
        with self._lock:
            if agent not in self.agents:
                self.agents.append(agent)
            last_user = ""
            for m in reversed(event.messages or []):
                if m.get("role") == "user":
                    last_user = " ".join(b.get("text", "") for b in m.get("content", []) if isinstance(b, dict))
                    break
            u = event.agent.event_loop_metrics.accumulated_usage
            self._usage_seen[agent] = (u.get("inputTokens", 0), u.get("outputTokens", 0))
            self._agent_tokens[agent] = [0, 0]
            self._agent_span[agent] = self._start(f"agent:{agent}", "agent", agent, agent, self.root, last_user)
        bus.publish("agent.status", {"agent_id": agent, "status": "running", "run_id": self.run_id})

    def _after_invocation(self, event: AfterInvocationEvent) -> None:
        agent = event.agent.name
        text = ""
        try:
            text = str(event.result) if event.result is not None else ""
        except Exception:
            pass
        self.last_text[agent] = text
        with self._lock:
            self._settle_usage(event.agent)
            self._end(f"agent:{agent}", output=text, tokens=tuple(self._agent_tokens.get(agent, [0, 0])))
        bus.publish("agent.status", {"agent_id": agent, "status": "idle", "run_id": self.run_id})

    def _before_model(self, event: BeforeModelCallEvent) -> None:
        agent = event.agent.name
        with self._lock:
            self._settle_usage(event.agent)
            model_id = ""
            try:
                model_id = event.agent.model.get_config().get("model_id", "")
            except Exception:
                pass
            self._start(f"model:{agent}", "model", model_id or "model", agent, self._agent_span.get(agent, self.root),
                        attrs={"model_id": model_id, "projected_input_tokens": getattr(event, "projected_input_tokens", None)})

    def _after_model(self, event: AfterModelCallEvent) -> None:
        agent = event.agent.name
        with self._lock:
            output, stop = "", None
            if event.stop_response is not None:
                stop = str(getattr(event.stop_response, "stop_reason", ""))
                msg = getattr(event.stop_response, "message", {}) or {}
                output = " ".join(b.get("text", "") for b in msg.get("content", []) if isinstance(b, dict) and "text" in b)
            span = self._open.get(f"model:{agent}")
            if span:
                self._last_model_span[agent] = span["id"]
            if event.exception is not None:
                self.errors += 1
                self._end(f"model:{agent}", status="error", error=f"{type(event.exception).__name__}: {event.exception}")
            else:
                self._end(f"model:{agent}", output=output, attrs={"stop_reason": stop})

    def _before_tool(self, event: BeforeToolCallEvent) -> None:
        agent = event.agent.name
        tu = event.tool_use
        name = tu.get("name", "tool")
        source = "mcp" if name not in _PLATFORM and name != "handoff_to_agent" else ("swarm" if name == "handoff_to_agent" else "platform")
        with self._lock:
            self._start(f"tool:{tu.get('toolUseId')}", "handoff" if name == "handoff_to_agent" else "tool", name, agent,
                        self._agent_span.get(agent, self.root), tu.get("input"), attrs={"source": source})
        if name == "handoff_to_agent":
            inp = tu.get("input") or {}
            with self._lock:
                self.handoffs.append({"from": agent, "to": inp.get("agent_name"), "reason": str(inp.get("message", ""))[:500],
                                      "ts": datetime.now(timezone.utc).isoformat()})

    def _after_tool(self, event: AfterToolCallEvent) -> None:
        tu = event.tool_use
        name = tu.get("name", "tool")
        status, error = "ok", None
        if event.cancel_message:
            status, error = "blocked", str(event.cancel_message)
        elif event.exception is not None:
            status, error = "error", f"{type(event.exception).__name__}: {event.exception}"
        elif isinstance(event.result, dict) and event.result.get("status") == "error":
            status, error = "error", _tool_result_text(event.result)[:500]
        with self._lock:
            self.tool_calls += 1
            if status == "error":
                self.errors += 1
            self._end(f"tool:{tu.get('toolUseId')}", status=status, output=_tool_result_text(event.result), error=error)

    def cost(self) -> float:
        return self.tokens_in / 1e6 * self.price_in + self.tokens_out / 1e6 * self.price_out

    def flush_totals(self) -> None:
        with session_scope() as db:
            run = db.get(Run, self.run_id)
            if run:
                run.tokens_in, run.tokens_out = self.tokens_in, self.tokens_out
                run.tool_calls, run.errors = self.tool_calls, self.errors
                run.cost_usd = self.cost()
                run.agents = list(self.agents)
                run.handoffs = list(self.handoffs)


class ApprovalGate(HookProvider):
    """Second line of defense: cancels any state-changing Wazuh tool call.

    The agents' MCP client already filters these tools out; this catches a server
    that renames or adds one.
    """

    def __init__(self, tracer: RunTracer | None = None):
        self.tracer = tracer

    def register_hooks(self, registry: HookRegistry) -> None:
        registry.add_callback(BeforeToolCallEvent, self._check)

    def _check(self, event: BeforeToolCallEvent) -> None:
        name = event.tool_use.get("name", "")
        if is_action_tool(name):
            event.cancel_tool = (f"'{name}' is an active-response tool and agents cannot call it. "
                                 "Use propose_action; the autonomy policy and human approvers decide execution.")


_PLATFORM = {"get_case", "search_cases", "create_case", "update_case", "add_entities", "link_mitre", "add_finding",
             "propose_action", "list_actions", "save_report", "propose_detection", "skills"}
