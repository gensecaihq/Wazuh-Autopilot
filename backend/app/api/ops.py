import hmac

from fastapi import APIRouter, Body, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from ..audit import audit_user
from ..catalog import ACTIONS
from ..db import get_db, utcnow
from ..events import bus
from ..ingest import ingest
from ..metrics import dashboard
from ..models import Action, Alert, Case, Comment, Finding, Run, TimelineEvent, User
from ..orchestrator import orchestrator
from ..policy import get_policy
from ..security import Principal, get_principal, require
from ..serializers import (action_out, alert_out, case_out, comment_out, finding_out, run_summary, timeline_out)
from ..settings_store import get_section
from .common import client_ip, not_found, page

router = APIRouter()


@router.get("/dashboard/summary")
def dashboard_summary(range: str = "24h", _: Principal = Depends(require("dashboard:read")), db: Session = Depends(get_db)):
    return dashboard(db, range)


# -- alerts --------------------------------------------------------------------
@router.get("/alerts")
def list_alerts(severity: str = "", status: str = "", q: str = "", agent: str = "", limit: int = 50, offset: int = 0,
                _: Principal = Depends(require("alerts:read")), db: Session = Depends(get_db)):
    query = db.query(Alert).order_by(Alert.ts.desc())
    if severity:
        query = query.filter(Alert.severity.in_(severity.split(",")))
    if status:
        query = query.filter(Alert.status.in_(status.split(",")))
    if agent:
        query = query.filter(or_(Alert.agent_id == agent, Alert.agent_name == agent))
    if q:
        like = f"%{q}%"
        query = query.filter(or_(Alert.rule_description.ilike(like), Alert.src_ip.ilike(like),
                                 Alert.agent_name.ilike(like), Alert.rule_id == q))
    return page(query, limit, offset, alert_out)


@router.get("/alerts/{alert_id}")
def get_alert(alert_id: str, _: Principal = Depends(require("alerts:read")), db: Session = Depends(get_db)):
    a = db.get(Alert, alert_id) or not_found("alert")
    return alert_out(a, raw=True)


@router.post("/alerts/{alert_id}/triage")
def triage_alert(alert_id: str, principal: Principal = Depends(require("workflows:run")), db: Session = Depends(get_db)):
    a = db.get(Alert, alert_id) or not_found("alert")
    wf = "incident-response" if a.severity in {"high", "critical"} else "alert-triage"
    audit_user(db, principal, "alert.triage_requested", a.wazuh_id)
    db.commit()
    return orchestrator.start_run(wf, {"alerts": [a.raw]}, trigger="manual", case_id=a.case_id, alert_ids=[a.id])


@router.post("/ingest/wazuh")
def ingest_wazuh(request: Request, payload: dict | list = Body(...), db: Session = Depends(get_db)):
    key = request.headers.get("x-autopilot-ingest-key", "")
    expected = get_section(db, "ingestion").get("ingest_key", "")
    if not (key and expected and hmac.compare_digest(key, expected)):
        principal = get_principal(request, db)
        if "alerts:ingest" not in principal.permissions:
            raise HTTPException(403, "missing permission: alerts:ingest")
    alerts = payload if isinstance(payload, list) else payload.get("alerts", [payload]) if isinstance(payload, dict) else []
    return ingest(alerts[:1000], source="webhook")


# -- cases -----------------------------------------------------------------------
def _case_counts(db: Session, ids: list[str]) -> tuple[dict, dict]:
    if not ids:
        return {}, {}
    alerts = dict(db.query(Alert.case_id, func.count(Alert.id)).filter(Alert.case_id.in_(ids)).group_by(Alert.case_id).all())
    pending = dict(db.query(Action.case_id, func.count(Action.id)).filter(Action.case_id.in_(ids),
                                                                        Action.status == "proposed").group_by(Action.case_id).all())
    return alerts, pending


@router.get("/cases")
def list_cases(status: str = "", severity: str = "", q: str = "", assignee: str = "", limit: int = 50, offset: int = 0,
               _: Principal = Depends(require("cases:read")), db: Session = Depends(get_db)):
    query = db.query(Case).order_by(Case.updated_at.desc())
    if status:
        query = query.filter(Case.status.in_(status.split(",")))
    if severity:
        query = query.filter(Case.severity.in_(severity.split(",")))
    if assignee:
        query = query.filter(Case.assignee_id == assignee)
    if q:
        like = f"%{q}%"
        num = q.upper().replace("INC-", "")
        query = query.filter(or_(Case.title.ilike(like), Case.summary.ilike(like),
                                 Case.number == int(num) if num.isdigit() else False))
    total = query.order_by(None).count()
    rows = query.limit(max(1, min(limit, 500))).offset(offset).all()
    alerts, pending = _case_counts(db, [c.id for c in rows])
    return {"items": [case_out(c, alerts.get(c.id, 0), pending.get(c.id, 0)) for c in rows], "total": total}


def _case_detail(db: Session, case: Case) -> dict:
    alerts, pending = _case_counts(db, [case.id])
    alert_rows = db.query(Alert).filter_by(case_id=case.id).order_by(Alert.ts.desc()).limit(200).all()
    runs = db.query(Run).filter_by(case_id=case.id).order_by(Run.started_at.desc()).all()
    return {
        **case_out(case, alerts.get(case.id, 0), pending.get(case.id, 0)),
        "timeline": [timeline_out(t) for t in db.query(TimelineEvent).filter_by(case_id=case.id).order_by(TimelineEvent.ts).all()],
        "findings": [finding_out(f) for f in db.query(Finding).filter_by(case_id=case.id).order_by(Finding.created_at).all()],
        "alerts": [alert_out(a) for a in alert_rows],
        "actions": [action_out(a, case.number) for a in db.query(Action).filter_by(case_id=case.id).order_by(Action.created_at).all()],
        "runs": [run_summary(r, case.number) for r in runs],
        "comments": [comment_out(c) for c in db.query(Comment).filter_by(case_id=case.id).order_by(Comment.created_at).all()],
    }


def _get_case(db: Session, case_id: str) -> Case:
    case = db.get(Case, case_id)
    if not case and case_id.upper().startswith("INC-") and case_id[4:].isdigit():
        case = db.query(Case).filter_by(number=int(case_id[4:])).first()
    return case or not_found("case")


@router.get("/cases/{case_id}")
def get_case(case_id: str, _: Principal = Depends(require("cases:read")), db: Session = Depends(get_db)):
    return _case_detail(db, _get_case(db, case_id))


class CasePatch(BaseModel):
    status: str | None = None
    severity: str | None = None
    assignee_id: str | None = None
    title: str | None = None


@router.patch("/cases/{case_id}")
def update_case(case_id: str, body: CasePatch, principal: Principal = Depends(require("cases:write")),
                db: Session = Depends(get_db)):
    case = _get_case(db, case_id)
    changes = []
    if body.status and body.status != case.status:
        changes.append(f"status {case.status} → {body.status}")
        case.status = body.status
        if body.status in {"resolved", "closed", "false_positive"}:
            case.resolved_at = utcnow()
    if body.severity and body.severity != case.severity:
        changes.append(f"severity {case.severity} → {body.severity}")
        case.severity = body.severity
    if body.assignee_id is not None:
        user = db.get(User, body.assignee_id) if body.assignee_id else None
        case.assignee_id = user.id if user else None
        changes.append(f"assigned to {user.name if user else 'nobody'}")
    if body.title:
        case.title = body.title
    if changes:
        db.add(TimelineEvent(case_id=case.id, kind="status", actor=principal.name, text="; ".join(changes)))
        audit_user(db, principal, "case.updated", f"INC-{case.number:04d}", {"changes": changes})
    db.commit()
    detail = _case_detail(db, case)
    bus.publish("case.updated", detail)
    return detail


class CommentIn(BaseModel):
    body: str


@router.post("/cases/{case_id}/comments")
def add_comment(case_id: str, body: CommentIn, principal: Principal = Depends(require("cases:write")),
                db: Session = Depends(get_db)):
    case = _get_case(db, case_id)
    if principal.kind != "user":
        raise HTTPException(400, "Comments require a user session")
    c = Comment(case_id=case.id, author_id=principal.id, body=body.body[:10000])
    db.add(c)
    db.add(TimelineEvent(case_id=case.id, kind="comment", actor=principal.name, text=body.body[:200]))
    db.commit()
    db.refresh(c)
    return comment_out(c)


class RunIn(BaseModel):
    workflow_id: str


@router.post("/cases/{case_id}/run")
def run_on_case(case_id: str, body: RunIn, principal: Principal = Depends(require("workflows:run")),
                db: Session = Depends(get_db)):
    case = _get_case(db, case_id)
    alerts = [a.raw for a in db.query(Alert).filter_by(case_id=case.id).order_by(Alert.ts.desc()).limit(3).all()]
    audit_user(db, principal, "workflow.run", body.workflow_id, {"case": f"INC-{case.number:04d}"})
    db.commit()
    try:
        return orchestrator.start_run(body.workflow_id, {"alerts": alerts}, trigger="manual", case_id=case.id)
    except ValueError as e:
        raise HTTPException(404, str(e))


# -- actions -----------------------------------------------------------------------
@router.get("/actions/catalog")
def action_catalog(_: Principal = Depends(require("actions:read"))):
    return ACTIONS


@router.get("/actions")
def list_actions(status: str = "", case_id: str = "", limit: int = 100, offset: int = 0,
                 _: Principal = Depends(require("actions:read")), db: Session = Depends(get_db)):
    query = db.query(Action, Case.number).outerjoin(Case, Case.id == Action.case_id).order_by(Action.created_at.desc())
    if status:
        query = query.filter(Action.status.in_(status.split(",")))
    if case_id:
        query = query.filter(Action.case_id == case_id)
    total = query.order_by(None).count()
    rows = query.limit(max(1, min(limit, 500))).offset(offset).all()
    return {"items": [action_out(a, n) for a, n in rows], "total": total}


def _action(db: Session, action_id: str) -> tuple[Action, int | None]:
    a = db.get(Action, action_id) or not_found("action")
    num = db.get(Case, a.case_id).number if a.case_id else None
    return a, num


@router.get("/actions/{action_id}")
def get_action(action_id: str, _: Principal = Depends(require("actions:read")), db: Session = Depends(get_db)):
    a, num = _action(db, action_id)
    return action_out(a, num)


class ApproveIn(BaseModel):
    note: str | None = None


@router.post("/actions/{action_id}/approve")
def approve_action(action_id: str, request: Request, body: ApproveIn = ApproveIn(),
                   principal: Principal = Depends(require("actions:approve")), db: Session = Depends(get_db)):
    a, num = _action(db, action_id)
    if a.status != "proposed":
        raise HTTPException(409, f"Action is {a.status}, not proposed")
    if a.expires_at and a.expires_at < utcnow():
        a.status = "expired"
        db.commit()
        raise HTTPException(409, "Action expired")
    a.status, a.approved_by_id, a.approved_by_name, a.approved_at = "approved", principal.id, principal.name, utcnow()
    if a.case_id:
        db.add(TimelineEvent(case_id=a.case_id, kind="action", actor=principal.name, ref_id=a.id,
                             text=f"Approved {a.type} on {a.target}" + (f": {body.note}" if body.note else "")))
    audit_user(db, principal, "action.approved", f"{a.type}:{a.target}", {"action_id": a.id, "note": body.note},
               client_ip(request))
    db.commit()
    bus.publish("action.updated", action_out(a, num))
    if a.autonomy == "supervised":
        orchestrator.submit_execution(a.id, principal.name)
    return action_out(a, num)


class RejectIn(BaseModel):
    reason: str


@router.post("/actions/{action_id}/reject")
def reject_action(action_id: str, body: RejectIn, request: Request,
                  principal: Principal = Depends(require("actions:approve")), db: Session = Depends(get_db)):
    a, num = _action(db, action_id)
    if a.status not in {"proposed", "approved"}:
        raise HTTPException(409, f"Action is {a.status}")
    a.status, a.rejected_reason = "rejected", body.reason
    a.approved_by_id, a.approved_by_name = principal.id, principal.name
    if a.case_id:
        db.add(TimelineEvent(case_id=a.case_id, kind="action", actor=principal.name, ref_id=a.id,
                             text=f"Rejected {a.type} on {a.target}: {body.reason}"))
    audit_user(db, principal, "action.rejected", f"{a.type}:{a.target}", {"action_id": a.id, "reason": body.reason},
               client_ip(request))
    db.commit()
    bus.publish("action.updated", action_out(a, num))
    return action_out(a, num)


@router.post("/actions/{action_id}/execute")
def execute_action(action_id: str, request: Request, principal: Principal = Depends(require("actions:execute")),
                   db: Session = Depends(get_db)):
    a, num = _action(db, action_id)
    if a.status != "approved":
        raise HTTPException(409, f"Action must be approved first (currently {a.status})")
    if get_policy(db).get("require_two_person") and a.approved_by_id == principal.id:
        raise HTTPException(403, "Two-person rule: the approver cannot also execute this action")
    audit_user(db, principal, "action.execute_requested", f"{a.type}:{a.target}", {"action_id": a.id}, client_ip(request))
    db.commit()
    orchestrator.submit_execution(a.id, principal.name)
    return action_out(a, num)


@router.post("/actions/{action_id}/rollback")
def rollback(action_id: str, request: Request, principal: Principal = Depends(require("actions:execute")),
             db: Session = Depends(get_db)):
    a, num = _action(db, action_id)
    if a.status not in {"executed", "verified"}:
        raise HTTPException(409, f"Only executed actions can be rolled back (currently {a.status})")
    audit_user(db, principal, "action.rollback_requested", f"{a.type}:{a.target}", {"action_id": a.id}, client_ip(request))
    db.commit()
    orchestrator.submit_rollback(a.id, principal.name)
    return action_out(a, num)
