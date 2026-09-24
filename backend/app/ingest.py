"""Alert ingestion (webhook + MCP polling), deterministic case grouping and workflow triggering."""

import json
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from .audit import audit
from .db import session_scope, utcnow
from .events import bus
from .models import Alert, Case, Run, TimelineEvent, Workflow
from .serializers import alert_out, case_out
from .settings_store import get_section

log = logging.getLogger(__name__)

SEVERITY_ORDER = ["informational", "low", "medium", "high", "critical"]


def level_to_severity(level: int) -> str:
    if level >= 15:
        return "critical"
    if level >= 12:
        return "high"
    if level >= 8:
        return "medium"
    if level >= 5:
        return "low"
    return "informational"


def _parse_ts(value) -> datetime:
    if not value:
        return utcnow()
    try:
        s = str(value).replace("Z", "+00:00")
        if len(s) > 5 and s[-5] in "+-" and s[-3] != ":":  # +0000 → +00:00
            s = s[:-2] + ":" + s[-2:]
        dt = datetime.fromisoformat(s)
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except ValueError:
        return utcnow()


def normalize(raw: dict) -> dict:
    rule = raw.get("rule") or {}
    agent = raw.get("agent") or {}
    data = raw.get("data") or {}
    geo = raw.get("GeoLocation") or {}
    mitre = []
    m = rule.get("mitre") or {}
    ids, tactics, techniques = m.get("id") or [], m.get("tactic") or [], m.get("technique") or []
    for i, tid in enumerate(ids):
        mitre.append({"technique_id": tid, "name": techniques[i] if i < len(techniques) else "",
                      "tactic": tactics[i] if i < len(tactics) else (tactics[0] if tactics else "")})
    level = int(rule.get("level") or 0)
    loc = geo.get("location") or {}
    wazuh_id = str(raw.get("id") or raw.get("_id") or f"{raw.get('timestamp')}-{rule.get('id')}-{agent.get('id')}")
    return {
        "wazuh_id": wazuh_id, "ts": _parse_ts(raw.get("timestamp") or raw.get("@timestamp")),
        "rule_id": str(rule.get("id") or ""), "rule_level": level,
        "rule_description": str(rule.get("description") or "")[:2000], "rule_groups": rule.get("groups") or [],
        "severity": level_to_severity(level), "agent_id": str(agent.get("id")) if agent.get("id") is not None else None,
        "agent_name": agent.get("name"), "agent_ip": agent.get("ip"),
        "src_ip": data.get("srcip") or data.get("src_ip") or (data.get("win", {}).get("eventdata", {}) or {}).get("ipAddress"),
        "src_country": geo.get("country_name"), "src_lat": loc.get("lat"), "src_lon": loc.get("lon"),
        "dst_user": data.get("dstuser") or data.get("user") or (data.get("win", {}).get("eventdata", {}) or {}).get("targetUserName"),
        "mitre": mitre, "raw": raw,
    }


def _pick_workflow(db: Session, severity: str) -> Workflow | None:
    rank = SEVERITY_ORDER.index(severity)
    best, best_rank = None, -1
    for wf in db.query(Workflow).filter_by(enabled=True).all():
        trig = wf.trigger or {}
        if trig.get("type") != "alert":
            continue
        need = SEVERITY_ORDER.index(trig.get("severity_min", "high")) if trig.get("severity_min") in SEVERITY_ORDER else 3
        if rank >= need and need > best_rank:
            best, best_rank = wf, need
    return best


def ingest(raws: list[dict], source: str = "webhook") -> dict:
    """Store alerts, group into cases, and start workflows for new incidents."""
    to_start: list[tuple[str, str, dict, str]] = []
    accepted, case_ids = 0, []
    with session_scope() as db:
        cfg = get_section(db, "ingestion")
        min_level = int(cfg.get("min_level", 10))
        group_window = timedelta(minutes=int(cfg.get("group_window_min", 60)))
        max_runs = int(cfg.get("max_runs_per_hour", 30))
        runs_last_hour = db.query(func.count(Run.id)).filter(Run.trigger == "alert",
                                                              Run.started_at >= utcnow() - timedelta(hours=1)).scalar() or 0
        for raw in raws:
            if not isinstance(raw, dict):
                continue
            fields = normalize(raw)
            if db.query(Alert.id).filter_by(wazuh_id=fields["wazuh_id"]).first():
                continue
            alert = Alert(**fields)
            db.add(alert)
            db.flush()
            accepted += 1
            if alert.rule_level < min_level:
                bus.publish("alert.ingested", alert_out(alert))
                continue
            group_key = f"{alert.rule_id}|{alert.src_ip or alert.agent_id or '-'}"
            case = (db.query(Case).filter(Case.group_key == group_key, Case.updated_at >= utcnow() - group_window,
                                          Case.status.notin_(["resolved", "closed", "false_positive"]))
                    .order_by(Case.updated_at.desc()).first())
            if case:
                alert.case_id, alert.status = case.id, "grouped"
                case.updated_at = utcnow()
                if SEVERITY_ORDER.index(alert.severity) > SEVERITY_ORDER.index(case.severity):
                    case.severity = alert.severity
                db.add(TimelineEvent(case_id=case.id, kind="alert", actor="wazuh", ref_id=alert.id,
                                     text=f"Grouped alert {alert.rule_id}: {alert.rule_description[:120]}"))
                bus.publish("alert.ingested", alert_out(alert))
                continue
            number = (db.query(func.max(Case.number)).scalar() or 0) + 1
            host = alert.agent_name or f"agent {alert.agent_id}"
            case = Case(number=number, title=f"{alert.rule_description.rstrip('.')[:180]} on {host}",
                        summary="Opened automatically from Wazuh; awaiting triage.", severity=alert.severity,
                        status="open", confidence=0.5, group_key=group_key, mitre=alert.mitre,
                        entities=[e for e in [
                            {"type": "host", "value": alert.agent_name, "role": "victim", "enrichment": {"agent_id": alert.agent_id}} if alert.agent_name else None,
                            {"type": "ip", "value": alert.src_ip, "role": "attacker", "enrichment": {"country": alert.src_country}} if alert.src_ip else None,
                        ] if e])
            db.add(case)
            db.flush()
            alert.case_id = case.id
            db.add(TimelineEvent(case_id=case.id, kind="alert", actor="wazuh", ref_id=alert.id,
                                 text=f"Alert {alert.rule_id} (level {alert.rule_level}) on {host}"))
            audit(db, "case.created", target=f"INC-{number:04d}", detail={"source": source, "alert": alert.wazuh_id})
            case_ids.append(case.id)
            bus.publish("case.created", case_out(case, 1))
            bus.publish("alert.ingested", alert_out(alert))
            wf = _pick_workflow(db, alert.severity)
            if wf and runs_last_hour < max_runs:
                runs_last_hour += 1
                to_start.append((wf.id, case.id, {"alerts": [raw]}, alert.id))
            elif wf:
                db.add(TimelineEvent(case_id=case.id, kind="status", actor="autopilot",
                                     text="Automatic triage skipped: hourly run budget reached"))
    from .orchestrator import orchestrator
    for wf_id, case_id, payload, alert_id in to_start:
        try:
            orchestrator.start_run(wf_id, payload, trigger="alert", case_id=case_id, alert_ids=[alert_id])
        except Exception:
            log.exception("failed to start workflow %s", wf_id)
    if case_ids:
        from .notify import notify
        notify("critical_case", f":rotating_light: {len(case_ids)} new incident(s) opened by Autopilot")
    return {"accepted": accepted, "case_ids": case_ids}


def _extract_alerts(text: str) -> list[dict]:
    try:
        data = json.loads(text)
    except ValueError:
        start = text.find("{")
        if start < 0:
            return []
        try:
            data = json.loads(text[start:])
        except ValueError:
            return []
    if isinstance(data, list):
        return [a for a in data if isinstance(a, dict)]
    for path in (("alerts",), ("data", "affected_items"), ("data", "alerts"), ("hits", "hits"), ("items",)):
        cur = data
        for p in path:
            cur = cur.get(p) if isinstance(cur, dict) else None
        if isinstance(cur, list):
            return [a.get("_source", a) if isinstance(a, dict) else a for a in cur]
    return []


class Poller:
    def __init__(self) -> None:
        self.last_poll_at: datetime | None = None
        self.last_error: str | None = None
        self.last_count = 0
        self._cursor: datetime | None = None

    def poll_once(self) -> int:
        from .swarm.mcp import result_text, wazuh
        with session_scope() as db:
            cfg = get_section(db, "ingestion")
            wazuh_settings = get_section(db, "wazuh")
        if cfg.get("mode") not in {"poll", "both"} or not wazuh.configured(wazuh_settings):
            return 0
        since = self._cursor or (utcnow() - timedelta(minutes=15))
        try:
            raw = wazuh.execute(wazuh_settings, "get_wazuh_alerts", {
                "limit": 500, "compact": False, "timestamp_start": since.strftime("%Y-%m-%dT%H:%M:%SZ")})
            alerts = _extract_alerts(result_text(raw))
            result = ingest(alerts, source="poll")
            if alerts:
                newest = max(_parse_ts(a.get("timestamp")) for a in alerts)
                self._cursor = max(since, newest - timedelta(seconds=1))
            self.last_error, self.last_count = None, result["accepted"]
            return result["accepted"]
        except Exception as e:
            self.last_error = f"{type(e).__name__}: {e}"
            log.warning("poll failed: %s", self.last_error)
            return 0
        finally:
            self.last_poll_at = utcnow()


poller = Poller()


def cron_matches(expr: str, dt: datetime) -> bool:
    """Minimal 5-field cron matcher (minute hour day month weekday; supports *, */n, a-b, a,b)."""
    try:
        fields = expr.split()
        if len(fields) != 5:
            return False
        values = [dt.minute, dt.hour, dt.day, dt.month, (dt.weekday() + 1) % 7]
        for field, value in zip(fields, values):
            ok = False
            for part in field.split(","):
                step = 1
                if "/" in part:
                    part, s = part.split("/")
                    step = int(s)
                if part == "*":
                    ok = ok or value % step == 0
                elif "-" in part:
                    a, b = map(int, part.split("-"))
                    ok = ok or (a <= value <= b and (value - a) % step == 0)
                else:
                    ok = ok or value == int(part)
            if not ok:
                return False
        return True
    except ValueError:
        return False
