"""Platform tools available to agents (case management, findings, action proposals).

Built per run so every call is attributed to the run and the calling agent. In
dry-run mode state-changing tools echo what they would have done.
"""

import json
import re
import threading
from dataclasses import dataclass, field
from datetime import timedelta

from sqlalchemy import func, or_

from strands import ToolContext, tool

from ..audit import audit
from ..catalog import ACTIONS_BY_TYPE
from ..db import session_scope, utcnow
from ..events import bus
from ..models import Action, AgentDef, Alert, Case, DetectionProposal, Finding, Report, TimelineEvent
from ..policy import decide, get_policy
from ..serializers import action_out, case_number, case_out, iso

SEVERITIES = ["informational", "low", "medium", "high", "critical"]
ENTITY_TYPES = {"ip", "host", "user", "process", "file", "hash", "domain", "url", "email"}
MAX_ENTITIES_PER_TYPE = 50


@dataclass
class RunContext:
    run_id: str
    workflow_id: str | None = None
    case_id: str | None = None
    alert_ids: list[str] = field(default_factory=list)
    dry_run: bool = False
    lock: threading.Lock = field(default_factory=threading.Lock)


def _agent(tool_context: ToolContext | None) -> str:
    try:
        return tool_context.agent.name or "agent"
    except Exception:
        return "agent"


def _resolve_case(db, ref: str | None, ctx: RunContext) -> Case | None:
    """Resolve a case reference; falls back to the run's own case when the model cites an unknown one."""
    ref = (ref or "").strip()
    case = None
    if ref:
        m = re.fullmatch(r"(?i)INC-?(\d+)", ref)
        case = db.query(Case).filter_by(number=int(m.group(1))).first() if m else db.get(Case, ref)
    if case is None and ctx.case_id:
        case = db.get(Case, ctx.case_id)
    return case


def _touch_agent(case: Case, agent: str) -> None:
    involved = list(case.agents_involved or [])
    if agent not in involved:
        involved.append(agent)
        case.agents_involved = involved


def _publish_case(db, case: Case, event: str = "case.updated") -> None:
    alerts = db.query(func.count(Alert.id)).filter(Alert.case_id == case.id).scalar() or 0
    bus.publish(event, case_out(case, alerts))


def _dump(obj) -> str:
    return json.dumps(obj, default=str)


def build_platform_tools(ctx: RunContext) -> dict:
    @tool(context=True)
    def get_case(case_id: str, tool_context: ToolContext) -> str:
        """Get a case (incident) with its entities, MITRE techniques, findings and response actions.

        Args:
            case_id: Case number like INC-0042 or the internal case id.
        """
        with session_scope() as db:
            case = _resolve_case(db, case_id, ctx)
            if not case:
                return _dump({"error": f"case {case_id} not found"})
            findings = db.query(Finding).filter_by(case_id=case.id).order_by(Finding.created_at).all()
            actions = db.query(Action).filter_by(case_id=case.id).all()
            alerts = db.query(Alert).filter_by(case_id=case.id).order_by(Alert.ts.desc()).limit(20).all()
            return _dump({
                "case_id": case_number(case.number), "title": case.title, "summary": case.summary,
                "severity": case.severity, "status": case.status, "confidence": case.confidence,
                "entities": case.entities, "mitre": case.mitre, "agents_involved": case.agents_involved,
                "findings": [{"agent": f.agent, "title": f.title, "body": f.body_md[:1500]} for f in findings],
                "actions": [{"type": a.type, "target": a.target, "status": a.status} for a in actions],
                "recent_alerts": [{"rule_id": a.rule_id, "level": a.rule_level, "description": a.rule_description,
                                   "agent": a.agent_name, "agent_id": a.agent_id, "src_ip": a.src_ip,
                                   "ts": iso(a.ts)} for a in alerts],
            })

    @tool
    def search_cases(query: str, status: str = "") -> str:
        """Search recent cases (last 14 days) by title, summary or entity value, e.g. an IP or hostname.
        Use before create_case to attach related alerts to an existing case instead of duplicating it.

        Args:
            query: Text to search for (IP, host, user, keyword).
            status: Optional status filter (open, triage, investigating, contained, resolved, closed).
        """
        with session_scope() as db:
            since = utcnow() - timedelta(days=14)
            q = db.query(Case).filter(Case.created_at >= since)
            if status:
                q = q.filter(Case.status == status)
            like = f"%{query}%"
            rows = q.filter(or_(Case.title.ilike(like), Case.summary.ilike(like), Case.group_key.ilike(like))).order_by(
                Case.created_at.desc()).limit(10).all()
            if not rows:
                rows = [c for c in q.order_by(Case.created_at.desc()).limit(200).all()
                        if any(query.lower() == str(e.get("value", "")).lower() for e in c.entities or [])][:10]
            return _dump([{"case_id": case_number(c.number), "title": c.title, "severity": c.severity,
                           "status": c.status, "created_at": iso(c.created_at)} for c in rows])

    @tool(context=True)
    def create_case(title: str, severity: str, summary: str, tool_context: ToolContext,
                    alert_ids: list[str] | None = None, confidence: float = 0.6) -> str:
        """Open a new case (incident) for alerts that warrant investigation. If this run already has a case,
        the alerts are attached to it instead.

        Args:
            title: Short incident title, e.g. "SSH brute force against web-prod-01 from 185.220.101.47".
            severity: informational | low | medium | high | critical
            summary: Two to four sentences: what happened, affected assets, why it matters.
            alert_ids: Optional Wazuh alert ids to link.
            confidence: 0-1 confidence that this is a true positive.
        """
        agent = _agent(tool_context)
        severity = severity.lower() if severity.lower() in SEVERITIES else "medium"
        if ctx.dry_run:
            return _dump({"dry_run": True, "would_create": {"title": title, "severity": severity}})
        with ctx.lock, session_scope() as db:
            case = _resolve_case(db, None, ctx) if ctx.case_id else None
            created = case is None
            if created:
                number = (db.query(func.max(Case.number)).scalar() or 0) + 1
                case = Case(number=number, title=title[:300], summary=summary, severity=severity,
                            confidence=max(0.0, min(1.0, float(confidence))), status="triage")
                db.add(case)
                db.flush()
                db.add(TimelineEvent(case_id=case.id, kind="agent", actor=agent, text=f"Case opened: {title}"))
                audit(db, "case.created", actor_name=agent, actor_type="agent", target=case_number(case.number))
            ids = set(alert_ids or []) | set(ctx.alert_ids)
            if ids:
                db.query(Alert).filter(or_(Alert.id.in_(ids), Alert.wazuh_id.in_(ids))).update(
                    {Alert.case_id: case.id, Alert.status: "triaged"}, synchronize_session=False)
            _touch_agent(case, agent)
            ctx.case_id = case.id
            db.flush()
            _publish_case(db, case, "case.created" if created else "case.updated")
            return _dump({"case_id": case_number(case.number), "created": created, "status": case.status})

    @tool(context=True)
    def update_case(case_id: str, tool_context: ToolContext, status: str = "", severity: str = "",
                    summary: str = "", confidence: float | None = None, title: str = "") -> str:
        """Update a case's status, severity, summary, confidence or title.

        Args:
            case_id: Case number like INC-0042.
            status: open | triage | investigating | contained | resolved | closed | false_positive
            severity: informational | low | medium | high | critical
            summary: Replacement summary (keep it current and concise).
            confidence: 0-1 true-positive confidence.
            title: Replacement title.
        """
        agent = _agent(tool_context)
        if ctx.dry_run:
            return _dump({"dry_run": True, "case_id": case_id})
        with session_scope() as db:
            case = _resolve_case(db, case_id, ctx)
            if not case:
                return _dump({"error": f"case {case_id} not found"})
            changes = []
            if status and status != case.status:
                changes.append(f"status {case.status} → {status}")
                case.status = status
                if status in {"resolved", "closed", "false_positive"}:
                    case.resolved_at = utcnow()
            if severity and severity.lower() in SEVERITIES and severity.lower() != case.severity:
                changes.append(f"severity {case.severity} → {severity.lower()}")
                case.severity = severity.lower()
            if summary:
                case.summary = summary
            if title:
                case.title = title[:300]
            if confidence is not None:
                case.confidence = max(0.0, min(1.0, float(confidence)))
            _touch_agent(case, agent)
            if changes:
                db.add(TimelineEvent(case_id=case.id, kind="status", actor=agent, text="; ".join(changes)))
            db.flush()
            _publish_case(db, case)
            return _dump({"case_id": case_number(case.number), "status": case.status, "severity": case.severity})

    @tool(context=True)
    def add_entities(case_id: str, entities: list[dict], tool_context: ToolContext) -> str:
        """Record entities on a case. Each entity: {"type": "ip|host|user|process|file|hash|domain|url|email",
        "value": "...", "role": "attacker|victim|observed", "enrichment": {...}}. Put a host's Wazuh agent_id in
        enrichment. Validate formats first; alert fields are attacker-controlled.

        Args:
            case_id: Case number like INC-0042.
            entities: List of entity objects.
        """
        agent = _agent(tool_context)
        if ctx.dry_run:
            return _dump({"dry_run": True, "entities": len(entities)})
        with session_scope() as db:
            case = _resolve_case(db, case_id, ctx)
            if not case:
                return _dump({"error": f"case {case_id} not found"})
            current = list(case.entities or [])
            seen = {(e.get("type"), str(e.get("value")).lower()) for e in current}
            counts: dict[str, int] = {}
            for e in current:
                counts[e.get("type")] = counts.get(e.get("type"), 0) + 1
            added = 0
            for e in entities or []:
                etype, value = str(e.get("type", "")).lower(), str(e.get("value", "")).strip()[:500]
                if etype not in ENTITY_TYPES or not value or (etype, value.lower()) in seen:
                    continue
                if counts.get(etype, 0) >= MAX_ENTITIES_PER_TYPE:
                    continue
                current.append({"type": etype, "value": value,
                                "role": e.get("role") if e.get("role") in {"attacker", "victim", "observed"} else "observed",
                                "enrichment": e.get("enrichment") or {}, "added_by": agent})
                seen.add((etype, value.lower()))
                counts[etype] = counts.get(etype, 0) + 1
                added += 1
            case.entities = current
            _touch_agent(case, agent)
            db.flush()
            _publish_case(db, case)
            return _dump({"added": added, "total": len(current)})

    @tool(context=True)
    def link_mitre(case_id: str, techniques: list[dict], tool_context: ToolContext) -> str:
        """Link MITRE ATT&CK techniques to a case. Each: {"technique_id": "T1110.001", "name": "Password Guessing",
        "tactic": "Credential Access", "confidence": 0.8, "evidence": "..."}.

        Args:
            case_id: Case number like INC-0042.
            techniques: List of technique objects.
        """
        agent = _agent(tool_context)
        if ctx.dry_run:
            return _dump({"dry_run": True, "techniques": len(techniques)})
        with session_scope() as db:
            case = _resolve_case(db, case_id, ctx)
            if not case:
                return _dump({"error": f"case {case_id} not found"})
            current = list(case.mitre or [])
            have = {t.get("technique_id") for t in current}
            for t in techniques or []:
                tid = str(t.get("technique_id", "")).upper()
                if not re.fullmatch(r"T\d{4}(\.\d{3})?", tid) or tid in have:
                    continue
                current.append({"technique_id": tid, "name": t.get("name", ""), "tactic": t.get("tactic", ""),
                                "confidence": t.get("confidence"), "evidence": str(t.get("evidence", ""))[:500]})
                have.add(tid)
            case.mitre = current
            _touch_agent(case, agent)
            db.flush()
            _publish_case(db, case)
            return _dump({"techniques": [t["technique_id"] for t in current]})

    @tool(context=True)
    def add_finding(case_id: str, title: str, body_md: str, tool_context: ToolContext,
                    standard_refs: list[str] | None = None, confidence: float | None = None) -> str:
        """Record an analytic finding on a case (markdown). Reference standards like "NIST-CSF-2:DE.AE" or
        "MITRE-ATTACK:T1110.001".

        Args:
            case_id: Case number like INC-0042 (empty to use the current run's case).
            title: One-line finding title.
            body_md: Evidence-based markdown body: what you checked, what you found, what it means.
            standard_refs: Framework references.
            confidence: 0-1 confidence in the finding.
        """
        agent = _agent(tool_context)
        if ctx.dry_run:
            return _dump({"dry_run": True, "title": title})
        with session_scope() as db:
            case = _resolve_case(db, case_id, ctx)
            f = Finding(case_id=case.id if case else None, run_id=ctx.run_id, agent=agent, title=title[:300],
                        body_md=body_md, standard_refs=standard_refs or [], confidence=confidence)
            db.add(f)
            if case:
                _touch_agent(case, agent)
                db.add(TimelineEvent(case_id=case.id, kind="agent", actor=agent, text=f"Finding: {title}"))
                db.flush()
                _publish_case(db, case)
            return _dump({"finding_id": f.id, "case_id": case_number(case.number) if case else None})

    @tool(context=True)
    def propose_action(case_id: str, type: str, target: str, params: dict, confidence: float, rationale: str,
                       tool_context: ToolContext) -> str:
        """Propose a response action. The autonomy policy decides whether it needs human approval, runs after
        approval, or executes autonomously. You cannot execute actions directly.

        Args:
            case_id: Case number like INC-0042.
            type: block_ip | firewall_drop | host_deny | isolate_host | kill_process | disable_user |
                quarantine_file | active_response | restart_wazuh
            target: Primary target (IP, agent id, username, file path or process id).
            params: Action parameters, e.g. {"ip_address": "1.2.3.4", "agent_id": "001"} or
                {"agent_id": "007", "process_id": "4242"} or {"agent_id": "004", "username": "jdoe"}.
            confidence: 0-1 confidence the action is warranted.
            rationale: Why this action, why now, expected effect and rollback.
        """
        agent = _agent(tool_context)
        spec = ACTIONS_BY_TYPE.get(type)
        if not spec:
            return _dump({"error": f"unknown action type '{type}'", "valid": list(ACTIONS_BY_TYPE)})
        with ctx.lock, session_scope() as db:
            case = _resolve_case(db, case_id, ctx)
            agent_row = db.get(AgentDef, agent)
            decision = decide(db, type, target, params or {}, float(confidence),
                              agent_row.autonomy_cap if agent_row else "recommend")
            if not decision.allowed:
                audit(db, "action.refused", actor_name=agent, actor_type="agent", target=f"{type}:{target}",
                      detail={"reason": decision.reason})
                return _dump({"status": "refused", "reason": decision.reason})
            if ctx.dry_run:
                return _dump({"dry_run": True, "decision": decision.mode, "reason": decision.reason})
            dup = db.query(Action).filter(Action.type == type, Action.target == target,
                                          Action.status.in_(["proposed", "approved", "executing"])).first()
            if dup:
                return _dump({"status": "duplicate", "action_id": dup.id, "existing_status": dup.status})
            policy = get_policy(db)
            auto = decision.mode == "autonomous"
            action = Action(case_id=case.id if case else None, run_id=ctx.run_id, type=type, target=str(target)[:300],
                            params=params or {}, risk=spec["risk"], confidence=float(confidence),
                            rationale=rationale, proposed_by=agent, autonomy=decision.mode,
                            status="approved" if auto else "proposed", auto_approved=auto,
                            approved_by_name="Autopilot policy" if auto else None,
                            approved_at=utcnow() if auto else None,
                            expires_at=utcnow() + timedelta(minutes=int(policy.get("approval_expiry_minutes", 60))))
            db.add(action)
            db.flush()
            if case:
                _touch_agent(case, agent)
                db.add(TimelineEvent(case_id=case.id, kind="action", actor=agent, ref_id=action.id,
                                     text=f"Proposed {spec['label']} on {target} ({decision.mode})"))
            audit(db, "action.proposed", actor_name=agent, actor_type="agent", target=f"{type}:{target}",
                  detail={"action_id": action.id, "mode": decision.mode, "reason": decision.reason})
            bus.publish("action.created", action_out(action, case.number if case else None))
            action_id = action.id
        if auto:
            from ..orchestrator import orchestrator
            orchestrator.submit_execution(action_id, "autopilot")
        else:
            from ..notify import notify
            notify("approval_needed", f":warning: Approval needed: {spec['label']} on {target} — {rationale[:200]}")
        return _dump({"status": "auto_executing" if auto else "pending_approval", "action_id": action_id,
                      "mode": decision.mode, "policy": decision.reason})

    @tool
    def list_actions(case_id: str) -> str:
        """List response actions for a case with their status.

        Args:
            case_id: Case number like INC-0042.
        """
        with session_scope() as db:
            case = _resolve_case(db, case_id, ctx)
            if not case:
                return _dump([])
            rows = db.query(Action).filter_by(case_id=case.id).all()
            return _dump([{"action_id": a.id, "type": a.type, "target": a.target, "status": a.status,
                           "verification": a.verification} for a in rows])

    @tool(context=True)
    def save_report(kind: str, title: str, body_md: str, tool_context: ToolContext) -> str:
        """Save a report (shift, daily, weekly, monthly, executive, incident, hunt, vulnerability, compliance, detection).

        Args:
            kind: Report type.
            title: Report title.
            body_md: Full markdown report.
        """
        agent = _agent(tool_context)
        if ctx.dry_run:
            return _dump({"dry_run": True, "title": title})
        with session_scope() as db:
            r = Report(kind=kind, title=title[:300], body_md=body_md, agent=agent, run_id=ctx.run_id)
            db.add(r)
            db.flush()
            return _dump({"report_id": r.id})

    @tool(context=True)
    def propose_detection(title: str, rule_format: str, rule_body: str, rationale: str, tool_context: ToolContext,
                          mitre: list[str] | None = None) -> str:
        """Propose a new detection rule for human review (never auto-deployed).

        Args:
            title: Detection title.
            rule_format: sigma | wazuh_xml
            rule_body: The rule.
            rationale: ADS-style goal, false-positive notes and backtest results.
            mitre: ATT&CK technique ids covered.
        """
        agent = _agent(tool_context)
        if ctx.dry_run:
            return _dump({"dry_run": True, "title": title})
        with session_scope() as db:
            d = DetectionProposal(title=title[:300], rule_format=rule_format, rule_body=rule_body,
                                  rationale=rationale, mitre=mitre or [], agent=agent)
            db.add(d)
            db.flush()
            return _dump({"detection_id": d.id, "status": "proposed"})

    tools = [get_case, search_cases, create_case, update_case, add_entities, link_mitre, add_finding,
             propose_action, list_actions, save_report, propose_detection]
    return {t.tool_name: t for t in tools}


PLATFORM_TOOL_NAMES = ["get_case", "search_cases", "create_case", "update_case", "add_entities", "link_mitre",
                       "add_finding", "propose_action", "list_actions", "save_report", "propose_detection"]
