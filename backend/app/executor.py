"""Executes approved response actions through the Wazuh MCP server and verifies them."""

import json
import logging
import re

from sqlalchemy.orm import Session

from .audit import audit
from .catalog import ACTIONS_BY_TYPE, mcp_arguments, missing_arguments, rollback_arguments, verify_arguments
from .db import session_scope, utcnow
from .events import bus
from .models import Action, Case, TimelineEvent
from .serializers import action_out
from .settings_store import get_section
from .swarm.mcp import result_text, wazuh

log = logging.getLogger(__name__)


def _publish(db: Session, action: Action) -> None:
    num = db.get(Case, action.case_id).number if action.case_id else None
    bus.publish("action.updated", action_out(action, num))


def _parse_verification(action_type: str, text: str) -> tuple[bool | None, str]:
    """Best-effort interpretation of a wazuh_check_* result. None = inconclusive."""
    lowered = text.lower()
    data = None
    start = text.find("{")
    if start >= 0:
        try:
            data = json.loads(text[start:])
        except ValueError:
            data = None
    if isinstance(data, dict) and isinstance(data.get("data"), dict):
        data = {**data["data"], **data}
    if isinstance(data, dict):
        for key in ("verified", "blocked", "is_blocked", "isolated", "is_isolated", "quarantined", "disabled"):
            if isinstance(data.get(key), bool):
                return data[key], f"{key}={data[key]}"
        if action_type == "kill_process":
            for key in ("running", "is_running", "exists"):
                if isinstance(data.get(key), bool):
                    return (not data[key]), f"{key}={data[key]}"
    if re.search(r"\b(not blocked|not isolated|not quarantined|still running|no evidence)\b", lowered):
        return False, text[:200]
    if re.search(r"\b(blocked|isolated|quarantined|disabled|terminated|not running)\b", lowered):
        return True, text[:200]
    return None, "verification result inconclusive"


def execute_action(action_id: str, actor: str) -> None:
    """Runs synchronously (call from a worker thread)."""
    with session_scope() as db:
        action = db.get(Action, action_id)
        if not action or action.status not in {"approved"}:
            return
        spec = ACTIONS_BY_TYPE[action.type]
        args = mcp_arguments(action.type, action.target, action.params)
        missing = missing_arguments(action.type, args)
        action.status = "executing"
        action.executed_by = actor
        action.executed_at = utcnow()
        db.flush()
        _publish(db, action)
        if missing:
            action.status = "failed"
            action.result = {"error": f"missing required arguments: {', '.join(missing)}", "arguments": args}
            _finish(db, action, actor, f"{spec['label']} failed: missing {', '.join(missing)}")
            return
        settings = get_section(db, "wazuh")

    dry_run = bool((action.params or {}).get("_dry_run"))
    try:
        if dry_run:
            raw = {"status": "success", "content": [{"text": json.dumps({"dry_run": True, "tool": spec["mcp_tool"], "arguments": args})}]}
        else:
            raw = wazuh.execute(settings, spec["mcp_tool"], args)
        text = result_text(raw)
        ok = raw.get("status") != "error"
        verification: dict = {"verified": None, "note": "no verification tool for this action"}
        vargs = verify_arguments(action.type, args)
        if ok and spec.get("verify_tool") and vargs and not dry_run:
            try:
                vraw = wazuh.execute(settings, spec["verify_tool"], vargs)
                verified, note = _parse_verification(action.type, result_text(vraw))
                verification = {"verified": verified, "note": note, "tool": spec["verify_tool"]}
            except Exception as e:
                verification = {"verified": None, "note": f"verification failed: {e}", "tool": spec["verify_tool"]}
        with session_scope() as db:
            action = db.get(Action, action_id)
            action.result = {"tool": spec["mcp_tool"], "arguments": args, "status": raw.get("status"), "output": text[:4000]}
            action.verification = verification
            if not ok:
                action.status = "failed"
            elif verification.get("verified") is True:
                action.status = "verified"
            else:
                action.status = "executed"
            _finish(db, action, actor, f"{spec['label']} on {action.target}: {action.status}")
        if ok and not dry_run:
            from .orchestrator import orchestrator
            orchestrator.start_verification(action_id)
    except Exception as e:
        log.exception("action %s failed", action_id)
        with session_scope() as db:
            action = db.get(Action, action_id)
            action.status = "failed"
            action.result = {"tool": spec["mcp_tool"], "arguments": args, "error": f"{type(e).__name__}: {e}"}
            _finish(db, action, actor, f"{spec['label']} on {action.target} failed: {e}")


def rollback_action(action_id: str, actor: str) -> None:
    with session_scope() as db:
        action = db.get(Action, action_id)
        if not action or action.status not in {"executed", "verified"}:
            return
        spec = ACTIONS_BY_TYPE[action.type]
        args = (action.result or {}).get("arguments") or mcp_arguments(action.type, action.target, action.params)
        rargs = rollback_arguments(action.type, args)
        settings = get_section(db, "wazuh")
    if not spec.get("rollback_tool") or rargs is None:
        with session_scope() as db:
            action = db.get(Action, action_id)
            action.result = {**(action.result or {}), "rollback_error": "this action cannot be rolled back automatically"}
            _publish(db, action)
        return
    try:
        raw = wazuh.execute(settings, spec["rollback_tool"], rargs)
        ok = raw.get("status") != "error"
        with session_scope() as db:
            action = db.get(Action, action_id)
            action.result = {**(action.result or {}), "rollback": {"tool": spec["rollback_tool"], "arguments": rargs,
                                                                   "status": raw.get("status"), "output": result_text(raw)[:2000]}}
            if ok:
                action.status = "rolled_back"
            _finish(db, action, actor, f"Rollback of {spec['label']} on {action.target}: {'done' if ok else 'failed'}")
    except Exception as e:
        with session_scope() as db:
            action = db.get(Action, action_id)
            action.result = {**(action.result or {}), "rollback_error": f"{type(e).__name__}: {e}"}
            _publish(db, action)


def _finish(db: Session, action: Action, actor: str, text: str) -> None:
    if action.case_id:
        db.add(TimelineEvent(case_id=action.case_id, kind="action", actor=actor, text=text, ref_id=action.id))
    audit(db, f"action.{action.status}", actor_name=actor, actor_type="user" if actor not in {"autopilot"} else "system",
          target=f"{action.type}:{action.target}", detail={"action_id": action.id, "result": action.result,
                                                            "verification": action.verification})
    db.flush()
    _publish(db, action)
    from .notify import notify
    if action.status == "failed":
        notify("action_failed", f":x: {text}")
