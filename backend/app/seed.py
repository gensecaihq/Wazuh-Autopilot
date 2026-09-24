"""First-boot seeding: roster, workflows, eval suites, admin user, and demo history."""

import logging
import random
from datetime import timedelta

from sqlalchemy.orm import Session

from .catalog import ACTIONS_BY_TYPE, DEFAULT_ACTION_RULES
from .config import get_config
from .db import Base, engine, session_scope, utcnow
from .models import (Action, AgentDef, Alert, AuditLog, Case, EvalSuite, Finding, Run, Setting, Span, TimelineEvent,
                     User, Workflow, new_id)
from .roster import AGENTS, EVAL_SUITES, WORKFLOWS
from .security import hash_password
from .settings_store import get_section, set_section

log = logging.getLogger(__name__)


def init_db() -> None:
    Base.metadata.create_all(engine)
    with session_scope() as db:
        _sync_roster(db)
        _seed_policy(db)
        _seed_admin(db)
    cfg = get_config()
    if cfg.seed_history:
        with session_scope() as db:
            if db.query(Run).count() == 0:
                log.info("seeding demo history")
                seed_history(db)


AGENT_SYNC_FIELDS = ["name", "codename", "persona", "description", "responsibilities", "tier", "category", "icon",
                     "avatar_color", "skills", "standards", "tools", "handoffs"]
WORKFLOW_SYNC_FIELDS = ["name", "description", "mode", "trigger", "entry_agent", "steps"]
EVAL_SYNC_FIELDS = ["name", "agent_id", "description", "cases", "evaluators"]


def _sync_row(row, defaults: dict, applied: dict, fields: list[str]) -> dict:
    """Field-level upgrade of a built-in row: a field is updated to the new default only if it still equals the
    default applied last time (i.e. an admin hasn't customized it). Returns the defaults now applied."""
    for f in fields:
        if f not in applied or getattr(row, f) == applied[f]:
            setattr(row, f, defaults[f])
    return {f: defaults[f] for f in fields}


def _sync_roster(db: Session) -> None:
    state = get_section(db, "roster_state")
    new_state = {"agents": {}, "workflows": {}, "evals": {}}
    for i, a in enumerate(AGENTS):
        row = db.get(AgentDef, a["id"])
        if not row:
            db.add(AgentDef(**a, sort_order=i))
            new_state["agents"][a["id"]] = {f: a[f] for f in AGENT_SYNC_FIELDS}
        else:
            new_state["agents"][a["id"]] = _sync_row(row, a, state.get("agents", {}).get(a["id"], {}), AGENT_SYNC_FIELDS)
    for i, w in enumerate(WORKFLOWS):
        row = db.get(Workflow, w["id"])
        if not row:
            db.add(Workflow(**w, sort_order=i))
            new_state["workflows"][w["id"]] = {f: w[f] for f in WORKFLOW_SYNC_FIELDS}
        else:
            new_state["workflows"][w["id"]] = _sync_row(row, w, state.get("workflows", {}).get(w["id"], {}),
                                                        WORKFLOW_SYNC_FIELDS)
    for e in EVAL_SUITES:
        row = db.get(EvalSuite, e["id"])
        if not row:
            db.add(EvalSuite(**e))
            new_state["evals"][e["id"]] = {f: e[f] for f in EVAL_SYNC_FIELDS}
        else:
            new_state["evals"][e["id"]] = _sync_row(row, e, state.get("evals", {}).get(e["id"], {}), EVAL_SYNC_FIELDS)
    db.flush()
    set_section(db, "roster_state", new_state)


def _seed_policy(db: Session) -> None:
    if not db.get(Setting, "policy"):
        policy = get_section(db, "policy")
        policy["action_rules"] = [dict(r) for r in DEFAULT_ACTION_RULES]
        set_section(db, "policy", policy)
    for key in ("ingestion",):  # persist generated secrets once
        if not db.get(Setting, key):
            set_section(db, key, get_section(db, key))


def _seed_admin(db: Session) -> None:
    cfg = get_config()
    if db.query(User).count() == 0 and cfg.admin_password:
        db.add(User(email=cfg.admin_email.lower(), name="Platform Admin", role="admin",
                    password_hash=hash_password(cfg.admin_password)))
        if cfg.demo_mode:
            for email, name, role in [("maya.chen@autopilot.local", "Maya Chen", "soc_manager"),
                                      ("sam.okafor@autopilot.local", "Sam Okafor", "responder"),
                                      ("lena.ivanova@autopilot.local", "Lena Ivanova", "analyst"),
                                      ("raj.patel@autopilot.local", "Raj Patel", "auditor")]:
                db.add(User(email=email, name=name, role=role, password_hash=hash_password(cfg.admin_password)))
        set_section(db, "setup", {"complete": True})


# ---------------------------------------------------------------------------
# Demo history
# ---------------------------------------------------------------------------
HOSTS = [("001", "web-prod-01", "10.0.1.11"), ("002", "web-prod-02", "10.0.1.12"), ("003", "db-prod-01", "10.0.2.21"),
         ("004", "dc-01", "10.0.0.10"), ("005", "fin-ws-17", "10.0.5.117"), ("006", "k8s-node-1", "10.0.3.31"),
         ("007", "k8s-node-2", "10.0.3.32"), ("009", "vpn-gw-01", "10.0.0.2"), ("010", "mail-01", "10.0.0.25"),
         ("011", "jump-01", "10.0.0.5")]
SOURCES = [("185.220.101.47", "Germany", 51.3, 9.5), ("45.155.205.233", "Russia", 55.7, 37.6),
           ("103.145.13.201", "Vietnam", 21.0, 105.8), ("198.51.100.23", "United States", 37.1, -95.7),
           ("91.240.118.172", "Netherlands", 52.4, 4.9), ("222.186.30.112", "China", 32.1, 118.8),
           ("179.43.128.10", "Brazil", -23.5, -46.6), ("196.251.83.5", "South Africa", -26.2, 28.0),
           ("5.188.206.14", "Ukraine", 50.4, 30.5), ("139.59.10.2", "India", 12.97, 77.6)]
SCENARIOS = [
    {"rule": "5763", "level": 10, "desc": "sshd: brute force trying to get access to the system. Authentication failed.",
     "groups": ["syslog", "sshd", "authentication_failures"], "mitre": [("T1110", "Brute Force", "Credential Access")],
     "hosts": ["001", "002", "009", "011"], "action": "block_ip"},
    {"rule": "31152", "level": 10, "desc": "Multiple SQL injection attempts from same source ip.",
     "groups": ["web", "accesslog", "attack"], "mitre": [("T1190", "Exploit Public-Facing Application", "Initial Access")],
     "hosts": ["001", "002"], "action": "block_ip"},
    {"rule": "60204", "level": 10, "desc": "Multiple Windows Logon Failures",
     "groups": ["windows", "authentication_success"], "mitre": [("T1078", "Valid Accounts", "Defense Evasion")],
     "hosts": ["004", "005"], "action": "disable_user"},
    {"rule": "550", "level": 7, "desc": "Integrity checksum changed.",
     "groups": ["ossec", "syscheck", "syscheck_entry_modified"], "mitre": [("T1098", "Account Manipulation", "Persistence")],
     "hosts": ["003", "011"], "action": None},
    {"rule": "521", "level": 11, "desc": "Possible kernel level rootkit",
     "groups": ["ossec", "rootcheck"], "mitre": [("T1496", "Resource Hijacking", "Impact")],
     "hosts": ["006", "007"], "action": "kill_process"},
    {"rule": "87105", "level": 12, "desc": "VirusTotal: Alert - /tmp/.x/kworkerd - 34 engines detected this file",
     "groups": ["virustotal"], "mitre": [("T1204", "User Execution", "Execution")],
     "hosts": ["005", "010"], "action": "quarantine_file"},
]
NOISE = [("5501", 3, "PAM: Login session opened.", ["pam", "syslog"]),
         ("5402", 3, "Successful sudo to ROOT executed.", ["sudo", "syslog"]),
         ("31101", 5, "Web server 400 error code.", ["web", "accesslog"]),
         ("60106", 3, "Windows Logon Success", ["windows", "authentication_success"]),
         ("533", 7, "Listened ports status (netstat) changed.", ["ossec"]),
         ("5710", 5, "sshd: Attempt to login using a non-existent user", ["syslog", "sshd", "invalid_login"])]
FLOW = ["triage", "correlation", "investigation", "threat-intel", "response-planner"]
TOOLS_BY_AGENT = {
    "triage": ["skills", "search_cases", "get_wazuh_alerts", "create_case", "add_entities", "update_case", "handoff_to_agent"],
    "correlation": ["skills", "search_security_events", "analyze_alert_patterns", "link_mitre", "add_finding", "handoff_to_agent"],
    "investigation": ["skills", "get_agent_processes", "get_agent_ports", "add_finding", "handoff_to_agent"],
    "threat-intel": ["skills", "check_ioc_reputation", "add_finding", "handoff_to_agent"],
    "response-planner": ["skills", "propose_action", "add_finding", "update_case"],
    "responder": ["skills", "wazuh_check_blocked_ip", "add_finding"],
    "vuln-management": ["skills", "get_wazuh_critical_vulnerabilities", "get_wazuh_vulnerability_summary", "save_report"],
    "threat-hunter": ["skills", "search_security_events", "analyze_alert_patterns", "save_report"],
    "detection-engineer": ["skills", "get_wazuh_rules_summary", "propose_detection"],
    "compliance": ["skills", "run_compliance_check", "get_iso27001_gap_analysis", "save_report"],
    "reporting": ["skills", "get_wazuh_alert_summary", "save_report"],
}


def _severity(level: int) -> str:
    from .ingest import level_to_severity
    return level_to_severity(level)


def _alert(ts, rule, level, desc, groups, host, src=None, mitre=None, user=None) -> Alert:
    aid, name, ip = host
    raw = {"id": new_id("wz")[3:], "timestamp": ts.isoformat(), "rule": {"id": rule, "level": level, "description": desc,
           "groups": groups}, "agent": {"id": aid, "name": name, "ip": ip}}
    if src:
        raw["data"] = {"srcip": src[0], **({"dstuser": user} if user else {})}
        raw["GeoLocation"] = {"country_name": src[1], "location": {"lat": src[2], "lon": src[3]}}
    if mitre:
        raw["rule"]["mitre"] = {"id": [m[0] for m in mitre], "technique": [m[1] for m in mitre], "tactic": [m[2] for m in mitre]}
    return Alert(wazuh_id=raw["id"], ts=ts, rule_id=rule, rule_level=level, rule_description=desc, rule_groups=groups,
                 severity=_severity(level), agent_id=aid, agent_name=name, agent_ip=ip,
                 src_ip=src[0] if src else None, src_country=src[1] if src else None,
                 src_lat=src[2] if src else None, src_lon=src[3] if src else None, dst_user=user,
                 mitre=[{"technique_id": m[0], "name": m[1], "tactic": m[2]} for m in mitre or []],
                 status="triaged" if level >= 10 else "new", raw=raw)


def _run_with_spans(db: Session, rnd: random.Random, start, workflow_id, workflow_name, mode, agents, case_id=None,
                    trigger="alert", fail=False) -> Run:
    run = Run(workflow_id=workflow_id, workflow_name=workflow_name, mode=mode, trigger=trigger, case_id=case_id,
              status="failed" if fail else "completed", started_at=start, input={"seeded": True})
    db.add(run)
    db.flush()
    root = Span(run_id=run.id, kind="run", name=workflow_name, started_at=start, attributes={"mode": mode})
    db.add(root)
    db.flush()
    t, tin, tout, calls, errors, handoffs = start, 0, 0, 0, 0, []
    for i, agent in enumerate(agents):
        a_start = t
        aspan = Span(run_id=run.id, parent_id=root.id, kind="agent", name=agent, agent_id=agent, started_at=a_start)
        db.add(aspan)
        db.flush()
        for tool in TOOLS_BY_AGENT.get(agent, ["skills"]):
            m_in, m_out = rnd.randint(2400, 9000), rnd.randint(80, 600)
            m_dur = rnd.randint(700, 4200)
            db.add(Span(run_id=run.id, parent_id=aspan.id, kind="model", name="claude-sonnet-5", agent_id=agent,
                        started_at=t, duration_ms=m_dur, tokens_in=m_in, tokens_out=m_out,
                        attributes={"model_id": "global.anthropic.claude-sonnet-5", "stop_reason": "tool_use"}))
            t += timedelta(milliseconds=m_dur)
            tin, tout = tin + m_in, tout + m_out
            status = "ok"
            if fail and i == len(agents) - 1 and tool != "skills":
                status = "error"
                errors += 1
            dur = rnd.randint(40, 1800) if tool not in {"skills"} else rnd.randint(3, 20)
            kind = "handoff" if tool == "handoff_to_agent" else "tool"
            db.add(Span(run_id=run.id, parent_id=aspan.id, kind=kind, name=tool, agent_id=agent, started_at=t,
                        duration_ms=dur, status=status, attributes={"source": "swarm" if kind == "handoff" else (
                            "platform" if tool in {"create_case", "add_entities", "update_case", "link_mitre", "add_finding",
                                                   "propose_action", "save_report", "search_cases", "propose_detection", "skills"} else "mcp")},
                        error="TimeoutError: MCP call exceeded 30s" if status == "error" else None))
            calls += 1
            t += timedelta(milliseconds=dur)
            if kind == "handoff" and i + 1 < len(agents):
                handoffs.append({"from": agent, "to": agents[i + 1], "reason": "specialist needed", "ts": t.isoformat()})
            if status == "error":
                break
        aspan.duration_ms = int((t - a_start).total_seconds() * 1000)
    run.finished_at = t
    run.duration_ms = int((t - start).total_seconds() * 1000)
    root.duration_ms = run.duration_ms
    root.status = "error" if fail else "ok"
    run.tokens_in, run.tokens_out, run.tool_calls, run.errors = tin, tout, calls, errors
    run.cost_usd = tin / 1e6 * 3 + tout / 1e6 * 15
    run.agents, run.handoffs = agents, handoffs
    run.output_md = "\n\n".join(f"### {a}\nCompleted." for a in agents)
    if fail:
        run.error = "TimeoutError: MCP call exceeded 30s"
    return run


def seed_history(db: Session, days: int = 7) -> None:
    rnd = random.Random(1337)
    now = utcnow()
    hosts = {h[0]: h for h in HOSTS}
    users = {u.role: u for u in db.query(User).all()}
    responder = users.get("responder") or users.get("admin")
    alerts = []
    # background noise, weekday-heavy
    for hour in range(days * 24, 0, -1):
        base = now - timedelta(hours=hour)
        volume = rnd.randint(8, 18) if base.weekday() < 5 and 7 <= base.hour <= 20 else rnd.randint(3, 8)
        for _ in range(volume):
            rule, level, desc, groups = rnd.choice(NOISE)
            alerts.append(_alert(base + timedelta(seconds=rnd.randint(0, 3599)), rule, level, desc, groups,
                                 rnd.choice(HOSTS), rnd.choice(SOURCES) if rule in {"5710", "31101"} else None))
    db.add_all(alerts)
    number = 0
    statuses = ["resolved"] * 6 + ["closed"] * 3 + ["false_positive"] + ["contained"] * 2 + ["investigating"]
    for i in range(34):
        sc = SCENARIOS[i % len(SCENARIOS)]
        start = now - timedelta(hours=rnd.uniform(1, days * 24 - 2))
        host = hosts[rnd.choice(sc["hosts"])]
        src = rnd.choice(SOURCES) if sc["rule"] in {"5712", "31106", "60204"} else None
        user = rnd.choice(["root", "admin", "svc_backup", "j.doe"]) if sc["rule"] in {"5712", "60204"} else None
        burst = [_alert(start + timedelta(seconds=15 * k), sc["rule"], sc["level"], sc["desc"], sc["groups"], host, src,
                        sc["mitre"], user) for k in range(rnd.randint(3, 40))]
        db.add_all(burst)
        number += 1
        status = "open" if start > now - timedelta(hours=3) else rnd.choice(statuses)
        severity = _severity(sc["level"] + rnd.choice([0, 0, 1, 2]))
        case = Case(number=number, title=f"{sc['desc'].rstrip('.')[:120]} on {host[1]}" + (f" from {src[0]}" if src else ""),
                    summary=f"Swarm-investigated incident on {host[1]}. " + ("External source " + src[0] + f" ({src[1]}). " if src else "")
                            + "See findings and timeline.", severity=severity, status=status,
                    confidence=round(rnd.uniform(0.6, 0.97), 2), created_at=start,
                    updated_at=start + timedelta(minutes=rnd.randint(5, 240)),
                    resolved_at=start + timedelta(minutes=rnd.randint(12, 180)) if status in {"resolved", "closed", "false_positive"} else None,
                    group_key=f"{sc['rule']}|{src[0] if src else host[0]}",
                    entities=[{"type": "host", "value": host[1], "role": "victim", "enrichment": {"agent_id": host[0]}}]
                             + ([{"type": "ip", "value": src[0], "role": "attacker", "enrichment": {"country": src[1]}}] if src else [])
                             + ([{"type": "user", "value": user, "role": "victim", "enrichment": {}}] if user else []),
                    mitre=[{"technique_id": m[0], "name": m[1], "tactic": m[2], "confidence": 0.8} for m in sc["mitre"]],
                    agents_involved=FLOW[:rnd.randint(3, 5)], assignee_id=rnd.choice([u.id for u in users.values()]) if users else None)
        db.add(case)
        db.flush()
        for a in burst:
            a.case_id = case.id
        fail = rnd.random() < 0.06
        run = _run_with_spans(db, rnd, start + timedelta(seconds=20), "incident-response", "Alert → Containment", "swarm",
                              case.agents_involved, case.id, fail=fail)
        db.add(TimelineEvent(case_id=case.id, ts=start, kind="alert", actor="wazuh", text=f"Alert {sc['rule']} on {host[1]}"))
        for j, agent in enumerate(case.agents_involved):
            db.add(TimelineEvent(case_id=case.id, ts=start + timedelta(seconds=30 + 25 * j), kind="agent", actor=agent,
                                 text={"triage": "Case triaged and entities extracted",
                                       "correlation": "Correlated related activity; mapped to ATT&CK",
                                       "investigation": "Host processes and ports reviewed",
                                       "threat-intel": "Indicators enriched (Admiralty B2)",
                                       "response-planner": "Containment plan proposed"}[agent]))
            db.add(Finding(case_id=case.id, run_id=run.id, agent=agent, created_at=start + timedelta(seconds=35 + 25 * j),
                           title={"triage": "Triage assessment", "correlation": "Correlated activity",
                                  "investigation": f"Host review of {host[1]}", "threat-intel": "Indicator enrichment",
                                  "response-planner": "Containment plan"}[agent],
                           body_md="Evidence-based summary recorded by the swarm (seeded demo history).",
                           standard_refs=["NIST-800-61r3:Respond"], confidence=0.8))
        if sc["action"] and "response-planner" in case.agents_involved and not fail:
            spec = ACTIONS_BY_TYPE[sc["action"]]
            auto = sc["action"] == "block_ip" and rnd.random() < 0.7
            outcome = rnd.choices(["verified", "executed", "rejected", "rolled_back"], [70, 15, 10, 5])[0]
            target = src[0] if sc["action"] == "block_ip" and src else (user if sc["action"] == "disable_user" else host[0])
            t_act = start + timedelta(minutes=rnd.randint(3, 20))
            act = Action(case_id=case.id, run_id=run.id, type=sc["action"], target=target or host[0],
                         params={"agent_id": host[0], **({"ip_address": src[0]} if src else {})}, risk=spec["risk"],
                         confidence=round(rnd.uniform(0.82, 0.97), 2), rationale="Proportionate containment (seeded).",
                         proposed_by="response-planner", status=outcome, autonomy="autonomous" if auto else "supervised",
                         auto_approved=auto and outcome != "rejected", created_at=t_act,
                         approved_by_id=None if auto else responder.id if responder else None,
                         approved_by_name="Autopilot policy" if auto else (responder.name if responder else None),
                         approved_at=t_act + timedelta(minutes=0 if auto else rnd.randint(2, 25)) if outcome != "rejected" else None,
                         executed_by="autopilot" if auto else (responder.name if responder else None),
                         executed_at=t_act + timedelta(minutes=rnd.randint(1, 30)) if outcome != "rejected" else None,
                         rejected_reason="Business-critical host; handled manually" if outcome == "rejected" else None,
                         verification={"verified": outcome == "verified", "note": "seeded", "tool": spec["verify_tool"]} if outcome != "rejected" else {},
                         result={"tool": spec["mcp_tool"], "status": "success"} if outcome != "rejected" else {})
            db.add(act)
            db.add(AuditLog(ts=t_act, actor_name="response-planner", actor_type="agent", action="action.proposed",
                            target=f"{act.type}:{act.target}"))
            if outcome != "rejected":
                db.add(AuditLog(ts=act.executed_at, actor_name=act.executed_by or "autopilot",
                                actor_type="system" if auto else "user", action=f"action.{outcome}",
                                target=f"{act.type}:{act.target}"))
    # scheduled workflows
    for d in range(days):
        day = now - timedelta(days=d)
        for wf_id, name, agents, hour in [("vulnerability-sweep", "Vulnerability sweep", ["vuln-management", "reporting"], 7),
                                          ("daily-briefing", "Daily SOC briefing", ["reporting"], 8),
                                          ("threat-hunt", "Scheduled threat hunt", ["threat-hunter", "detection-engineer"], 0),
                                          ("threat-hunt", "Scheduled threat hunt", ["threat-hunter", "detection-engineer"], 12)]:
            start = day.replace(hour=hour, minute=0, second=0, microsecond=0)
            if start < now:
                _run_with_spans(db, rnd, start, wf_id, name, "graph", agents, trigger="schedule", fail=rnd.random() < 0.04)
    for u in users.values():
        db.add(AuditLog(ts=now - timedelta(hours=rnd.randint(1, 48)), actor_id=u.id, actor_name=u.name,
                        actor_type="user", action="auth.login", target=u.email))
    db.flush()
