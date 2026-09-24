import asyncio
import time
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..audit import audit_user
from ..catalog import ACTIONS_BY_TYPE
from ..config import VERSION
from ..db import get_db, utcnow
from ..events import bus
from ..ingest import poller
from ..metrics import timeseries
from ..models import AgentDef, AuditLog, DetectionProposal, Report, Run
from ..orchestrator import orchestrator
from ..policy import LEVELS, get_policy
from ..security import Principal, get_principal, require, require_or_setup
from ..serializers import iso
from ..settings_store import PROVIDERS, PUBLIC_SECTIONS, all_settings, get_section, set_section
from ..swarm.mcp import wazuh
from ..swarm.providers import build_model
from .common import client_ip, page

router = APIRouter()


# -- policy ------------------------------------------------------------------------------
@router.get("/policy")
def read_policy(_: Principal = Depends(require("policy:read")), db: Session = Depends(get_db)):
    return get_policy(db)


@router.put("/policy")
def write_policy(body: dict, request: Request, principal: Principal = Depends(require("policy:write")),
                 db: Session = Depends(get_db)):
    if "autonomy_level" in body and body["autonomy_level"] not in LEVELS:
        raise HTTPException(400, f"autonomy_level must be one of {LEVELS}")
    for r in body.get("action_rules") or []:
        if r.get("type") not in ACTIONS_BY_TYPE:
            raise HTTPException(400, f"unknown action type {r.get('type')}")
        if r.get("autonomy", "inherit") not in {"inherit", "manual", "supervised", "autonomous"}:
            raise HTTPException(400, "invalid rule autonomy")
    before = get_policy(db)
    allowed = {"autonomy_level", "action_rules", "protected_targets", "approval_expiry_minutes",
               "require_two_person", "business_hours_only"}
    set_section(db, "policy", {k: v for k, v in body.items() if k in allowed})
    audit_user(db, principal, "policy.updated", "autonomy policy",
               {"autonomy_level": [before.get("autonomy_level"), body.get("autonomy_level", before.get("autonomy_level"))]},
               client_ip(request))
    db.commit()
    return get_policy(db)


# -- audit -------------------------------------------------------------------------------
@router.get("/audit")
def audit_log(actor: str = "", action: str = "", since: str = "", limit: int = 100, offset: int = 0,
              _: Principal = Depends(require("audit:read")), db: Session = Depends(get_db)):
    q = db.query(AuditLog).order_by(AuditLog.ts.desc())
    if actor:
        q = q.filter(AuditLog.actor_name.ilike(f"%{actor}%"))
    if action:
        q = q.filter(AuditLog.action.ilike(f"{action}%"))
    if since:
        from ..ingest import _parse_ts
        q = q.filter(AuditLog.ts >= _parse_ts(since))
    return page(q, limit, offset, lambda a: {
        "id": a.id, "ts": iso(a.ts), "actor": {"id": a.actor_id, "name": a.actor_name, "type": a.actor_type},
        "action": a.action, "target": a.target, "detail": a.detail or {}, "ip": a.ip})


# -- settings ------------------------------------------------------------------------------
@router.get("/settings")
def read_settings(_: Principal = Depends(require("settings:read")), db: Session = Depends(get_db)):
    return all_settings(db)


@router.put("/settings")
def write_settings(body: dict, request: Request, principal: Principal = Depends(require("settings:write")),
                   db: Session = Depends(get_db)):
    changed = []
    for section, value in body.items():
        if section not in PUBLIC_SECTIONS or not isinstance(value, dict):
            continue
        set_section(db, section, value)
        changed.append(section)
    if "model" in body and body["model"].get("provider") not in {None, *[p["id"] for p in PROVIDERS]}:
        raise HTTPException(400, "unknown model provider")
    audit_user(db, principal, "settings.updated", ",".join(changed), {"sections": changed}, client_ip(request))
    db.commit()
    if "wazuh" in changed:
        wazuh.close()
    return all_settings(db)


@router.get("/settings/providers")
def providers(_: Principal | None = Depends(require_or_setup("settings:read"))):
    return PROVIDERS


@router.post("/settings/test/wazuh")
def test_wazuh(body: dict | None = None, _: Principal | None = Depends(require_or_setup("settings:read")),
               db: Session = Depends(get_db)):
    settings = get_section(db, "wazuh")
    for k, v in (body or {}).items():
        if k in {"mcp_url", "api_key", "verify_tls"} and not (isinstance(v, str) and v.startswith("••••")):
            settings[k] = v
    return wazuh.test(settings)


@router.post("/settings/test/model")
def test_model(body: dict | None = None, _: Principal | None = Depends(require_or_setup("settings:read")),
               db: Session = Depends(get_db)):
    settings = get_section(db, "model")
    for k, v in (body or {}).items():
        if v not in (None, "") and not (isinstance(v, str) and v.startswith("••••")):
            settings[k] = v
    started = time.time()
    try:
        from strands import Agent
        agent = Agent(model=build_model(settings), callback_handler=None,
                      system_prompt="You are a connectivity check. Reply with exactly: OK")
        sample = str(agent("Reply with OK"))[:200]
        return {"ok": True, "latency_ms": int((time.time() - started) * 1000), "provider": settings.get("provider"),
                "model_id": settings.get("model_id"), "sample": sample.strip()}
    except Exception as e:
        return {"ok": False, "latency_ms": int((time.time() - started) * 1000), "provider": settings.get("provider"),
                "model_id": settings.get("model_id"), "error": f"{type(e).__name__}: {str(e)[:400]}"}


@router.post("/settings/test/notifications")
def test_notifications(_: Principal = Depends(require("settings:write")), db: Session = Depends(get_db)):
    from ..notify import send_slack
    url = get_section(db, "notifications").get("slack_webhook_url")
    if not url:
        return {"ok": False, "error": "No Slack webhook URL configured"}
    ok, err = send_slack(url, ":white_check_mark: Wazuh Autopilot test notification")
    return {"ok": ok, "error": err}


# -- system health & metrics -----------------------------------------------------------------
@router.get("/system/health")
def system_health(_: Principal = Depends(require("dashboard:read")), db: Session = Depends(get_db)):
    now = utcnow()
    comps = []
    t0 = time.time()
    try:
        db.execute(text("SELECT 1"))
        comps.append({"id": "database", "name": "Database", "status": "healthy", "latency_ms": int((time.time() - t0) * 1000),
                      "detail": db.bind.dialect.name})
    except Exception as e:
        comps.append({"id": "database", "name": "Database", "status": "down", "latency_ms": None, "detail": str(e)})
    comps.append({"id": "api", "name": "API", "status": "healthy", "latency_ms": 0, "detail": f"v{VERSION}"})
    w = get_section(db, "wazuh")
    if not wazuh.configured(w):
        comps.append({"id": "wazuh_mcp", "name": "Wazuh MCP Server", "status": "unknown", "latency_ms": None,
                      "detail": "Not configured"})
    else:
        t0 = time.time()
        tools = wazuh.agent_tools(w)
        comps.append({"id": "wazuh_mcp", "name": "Wazuh MCP Server", "status": "healthy" if tools else "down",
                      "latency_ms": int((time.time() - t0) * 1000),
                      "detail": f"{len(tools)} read tools available to agents" if tools else (wazuh.last_error or "unreachable")})
    m = get_section(db, "model")
    recent = db.query(Run.status).filter(Run.started_at >= now - timedelta(hours=1)).all()
    failed = sum(1 for (s,) in recent if s == "failed")
    comps.append({"id": "model", "name": f"Model ({m.get('provider')})",
                  "status": "degraded" if recent and failed / len(recent) > 0.3 else "healthy", "latency_ms": None,
                  "detail": f"{m.get('model_id')} · {failed}/{len(recent)} runs failed in the last hour"})
    comps.append({"id": "scheduler", "name": "Scheduler", "status": "healthy", "latency_ms": None,
                  "detail": f"{orchestrator.running} runs in progress"})
    ing = get_section(db, "ingestion")
    poll_status = "healthy" if not poller.last_error else "degraded"
    if ing.get("mode") == "webhook":
        detail = "Webhook mode"
    else:
        detail = (f"Last poll {iso(poller.last_poll_at)} · {poller.last_count} new" if poller.last_poll_at else "Waiting for first poll")
        if poller.last_error:
            detail = poller.last_error
    comps.append({"id": "ingestion", "name": "Alert ingestion", "status": poll_status, "latency_ms": None, "detail": detail})
    for c in comps:
        c["checked_at"] = iso(now)
    from ..metrics import agent_health
    health = agent_health(db)
    return {"components": comps, "swarm": {
        "agents_total": db.query(AgentDef).count(),
        "agents_healthy": sum(1 for h in health.values() if h["status"] in {"healthy", "idle"}),
        "runs_running": orchestrator.running,
        "queue_depth": db.query(Run).filter(Run.status == "queued").count()}}


@router.get("/metrics/timeseries")
def metrics_timeseries(metric: str = "runs", range: str = "24h", agent_id: str = "",
                       _: Principal = Depends(require("runs:read")), db: Session = Depends(get_db)):
    if metric not in {"runs", "tokens", "latency", "errors", "cost", "tool_calls"}:
        raise HTTPException(400, "unknown metric")
    return timeseries(db, metric, range, agent_id or None)


# -- reports & detections -----------------------------------------------------------------------
@router.get("/reports")
def list_reports(kind: str = "", limit: int = 50, offset: int = 0, _: Principal = Depends(require("cases:read")),
                 db: Session = Depends(get_db)):
    q = db.query(Report).order_by(Report.created_at.desc())
    if kind:
        q = q.filter(Report.kind == kind)
    return page(q, limit, offset, lambda r: {"id": r.id, "kind": r.kind, "title": r.title, "body_md": r.body_md,
                                             "agent": r.agent, "run_id": r.run_id, "created_at": iso(r.created_at)})


@router.get("/detections")
def list_detections(_: Principal = Depends(require("cases:read")), db: Session = Depends(get_db)):
    rows = db.query(DetectionProposal).order_by(DetectionProposal.created_at.desc()).limit(200).all()
    return {"items": [{"id": d.id, "title": d.title, "rule_format": d.rule_format, "rule_body": d.rule_body,
                       "rationale": d.rationale, "mitre": d.mitre, "agent": d.agent, "status": d.status,
                       "created_at": iso(d.created_at)} for d in rows], "total": len(rows)}


class DetectionStatus(BaseModel):
    status: str


@router.patch("/detections/{det_id}")
def review_detection(det_id: str, body: DetectionStatus, principal: Principal = Depends(require("cases:write")),
                     db: Session = Depends(get_db)):
    d = db.get(DetectionProposal, det_id)
    if not d:
        raise HTTPException(404, "detection not found")
    if body.status not in {"proposed", "accepted", "rejected"}:
        raise HTTPException(400, "invalid status")
    d.status = body.status
    audit_user(db, principal, f"detection.{body.status}", d.title)
    db.commit()
    return {"id": d.id, "status": d.status}


# -- live events -----------------------------------------------------------------------------------
@router.get("/events/stream")
async def event_stream(request: Request, principal: Principal = Depends(get_principal)):
    queue = bus.subscribe()

    async def gen():
        try:
            yield "event: hello\ndata: {}\n\n"
            while True:
                if await request.is_disconnected():
                    break
                try:
                    msg = await asyncio.wait_for(queue.get(), timeout=15)
                    yield msg
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
        finally:
            bus.unsubscribe(queue)

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
