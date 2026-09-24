"""ORM → API contract dicts (see docs/API.md)."""

from .catalog import ACTIONS_BY_TYPE
from .models import Action, Alert, AgentDef, Case, Comment, Finding, Run, Span, TimelineEvent, User
from .rbac import ROLES, permissions_for
from .standards import standard_ref


def iso(dt):
    return dt.isoformat() if dt else None


def case_number(n: int | None) -> str | None:
    return f"INC-{n:04d}" if n is not None else None


def user_out(u: User) -> dict:
    return {
        "id": u.id, "email": u.email, "name": u.name, "role": u.role,
        "role_label": ROLES.get(u.role, {}).get("label", u.role), "permissions": permissions_for(u.role),
        "active": u.active, "last_login_at": iso(u.last_login_at), "created_at": iso(u.created_at),
        "avatar_initials": "".join(p[0] for p in u.name.split()[:2]).upper() or u.email[:2].upper(),
    }


def alert_out(a: Alert, raw: bool = False) -> dict:
    out = {
        "id": a.id, "wazuh_id": a.wazuh_id, "ts": iso(a.ts), "rule_id": a.rule_id, "rule_level": a.rule_level,
        "rule_description": a.rule_description, "rule_groups": a.rule_groups or [], "severity": a.severity,
        "agent_id": a.agent_id, "agent_name": a.agent_name, "src_ip": a.src_ip, "src_country": a.src_country,
        "dst_user": a.dst_user, "mitre": a.mitre or [], "status": a.status, "case_id": a.case_id,
    }
    if raw:
        out["raw"] = a.raw
    return out


def action_out(a: Action, case_num: int | None = None) -> dict:
    spec = ACTIONS_BY_TYPE.get(a.type, {})
    return {
        "id": a.id, "case_id": a.case_id, "case_number": case_number(case_num), "plan_id": a.plan_id, "type": a.type,
        "label": spec.get("label", a.type), "target": a.target, "params": a.params or {}, "risk": a.risk,
        "confidence": a.confidence, "rationale": a.rationale, "proposed_by": a.proposed_by, "status": a.status,
        "autonomy": a.autonomy, "auto_approved": a.auto_approved,
        "approved_by": {"id": a.approved_by_id, "name": a.approved_by_name} if a.approved_by_name else None,
        "approved_at": iso(a.approved_at), "rejected_reason": a.rejected_reason, "executed_by": a.executed_by,
        "executed_at": iso(a.executed_at), "result": a.result or {}, "verification": a.verification or {},
        "created_at": iso(a.created_at), "expires_at": iso(a.expires_at), "d3fend": spec.get("d3fend", ""),
        "mcp_tool": spec.get("mcp_tool"), "reversible": spec.get("reversible", False),
    }


def case_out(c: Case, alert_count: int = 0, pending_actions: int = 0) -> dict:
    return {
        "id": c.id, "number": case_number(c.number), "title": c.title, "summary": c.summary,
        "severity": c.severity, "status": c.status, "confidence": c.confidence,
        "assignee": {"id": c.assignee.id, "name": c.assignee.name} if c.assignee else None,
        "created_at": iso(c.created_at), "updated_at": iso(c.updated_at), "alert_count": alert_count,
        "entity_count": len(c.entities or []), "mitre": c.mitre or [], "agents_involved": c.agents_involved or [],
        "pending_actions": pending_actions, "entities": c.entities or [],
    }


def timeline_out(t: TimelineEvent) -> dict:
    return {"id": t.id, "ts": iso(t.ts), "kind": t.kind, "actor": t.actor, "text": t.text, "ref_id": t.ref_id}


def finding_out(f: Finding) -> dict:
    return {"id": f.id, "agent": f.agent, "title": f.title, "body_md": f.body_md,
            "standard_refs": f.standard_refs or [], "confidence": f.confidence, "created_at": iso(f.created_at),
            "run_id": f.run_id}


def comment_out(c: Comment) -> dict:
    return {"id": c.id, "author": {"id": c.author.id, "name": c.author.name} if c.author else None,
            "body": c.body, "created_at": iso(c.created_at)}


def run_summary(r: Run, case_num: int | None = None) -> dict:
    return {
        "id": r.id, "workflow_id": r.workflow_id, "workflow_name": r.workflow_name, "mode": r.mode,
        "status": r.status, "trigger": r.trigger, "case_id": r.case_id, "case_number": case_number(case_num),
        "started_at": iso(r.started_at), "finished_at": iso(r.finished_at), "duration_ms": r.duration_ms,
        "agents": r.agents or [], "tokens_in": r.tokens_in, "tokens_out": r.tokens_out,
        "cost_usd": round(r.cost_usd or 0, 4), "tool_calls": r.tool_calls, "errors": r.errors,
        "dry_run": r.dry_run, "error": r.error,
    }


def span_out(s: Span) -> dict:
    return {
        "id": s.id, "parent_id": s.parent_id, "kind": s.kind, "name": s.name, "agent_id": s.agent_id,
        "status": s.status, "started_at": iso(s.started_at), "duration_ms": s.duration_ms,
        "tokens_in": s.tokens_in, "tokens_out": s.tokens_out, "attributes": s.attributes or {},
        "input_preview": s.input_preview, "output_preview": s.output_preview, "error": s.error,
    }


def run_out(r: Run, spans: list[Span], case_num: int | None = None) -> dict:
    return {**run_summary(r, case_num), "input": r.input or {}, "output_md": r.output_md,
            "handoffs": r.handoffs or [], "spans": [span_out(s) for s in spans]}


def agent_out(a: AgentDef, skills_index: dict, health: dict, model_settings: dict) -> dict:
    override = a.model_override or None
    return {
        "id": a.id, "name": a.name, "codename": a.codename, "persona": a.persona, "avatar_color": a.avatar_color,
        "icon": a.icon, "tier": a.tier, "category": a.category, "enabled": a.enabled,
        "status": "disabled" if not a.enabled else health.get("_status", "idle"),
        "description": a.description,
        "skills": [{"id": s, "name": skills_index.get(s, {}).get("name", s)} for s in a.skills or []],
        "standards": [standard_ref(s) for s in a.standards or []], "tools_count": len(a.tools or []),
        "handoffs": a.handoffs or [],
        "model": {"provider": (override or model_settings).get("provider"),
                  "model_id": (override or model_settings).get("model_id"), "inherited": override is None},
        "autonomy_cap": a.autonomy_cap, "temperature": a.temperature, "max_tokens": a.max_tokens,
        "system_prompt_extra": a.system_prompt_extra,
        "health": {k: v for k, v in health.items() if not k.startswith("_")},
    }
