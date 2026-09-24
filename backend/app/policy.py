"""Autonomy policy engine.

Levels (global, per action rule, and capped per agent):
  observe     agents analyze only; action proposals are refused
  recommend   agents propose; a human approves AND executes          -> "manual"
  supervised  a human approves; the platform executes automatically  -> "supervised"
  autonomous  eligible actions auto-execute; others fall back to supervised
Fail-secure: anything uncertain resolves to the more restrictive outcome.
"""

import ipaddress
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from .catalog import ACTIONS_BY_TYPE, DEFAULT_ACTION_RULES
from .db import utcnow
from .models import Action
from .settings_store import get_section

LEVELS = ["observe", "recommend", "supervised", "autonomous"]
LEVEL_TO_MODE = {"recommend": "manual", "supervised": "supervised", "autonomous": "autonomous"}
MODE_RANK = {"manual": 1, "supervised": 2, "autonomous": 3}


@dataclass
class Decision:
    allowed: bool
    mode: str = "manual"       # manual | supervised | autonomous
    reasons: list[str] | None = None

    @property
    def reason(self) -> str:
        return "; ".join(self.reasons or [])


def get_policy(db: Session) -> dict:
    policy = get_section(db, "policy")
    rules = {r["type"]: r for r in DEFAULT_ACTION_RULES}
    for r in policy.get("action_rules") or []:
        rules[r["type"]] = {**rules.get(r["type"], {}), **r}
    policy["action_rules"] = [rules[a] for a in ACTIONS_BY_TYPE if a in rules]
    return policy


def _in_network(value: str, entries: list[str]) -> bool:
    try:
        ip = ipaddress.ip_address(value)
    except ValueError:
        return False
    for entry in entries:
        try:
            if ip in ipaddress.ip_network(entry, strict=False):
                return True
        except ValueError:
            continue
    return False


def protected_hit(policy: dict, action_type: str, target: str, params: dict) -> str | None:
    pt = policy.get("protected_targets") or {}
    values = {str(target or "")} | {str(v) for k, v in (params or {}).items()
                                    if k in {"ip_address", "src_ip", "agent_id", "username", "hostname", "host"}}
    for v in values:
        if not v:
            continue
        if _in_network(v, pt.get("ips") or []):
            return f"target {v} is a protected IP"
        if v.lower() in {h.lower() for h in pt.get("hosts") or []}:
            return f"target {v} is a protected host"
        if v in set(pt.get("users") or []):
            return f"target {v} is a protected user"
        if v in set(pt.get("agent_ids") or []):
            return f"agent {v} is protected"
    return None


def _business_hours(now: datetime) -> bool:
    return now.weekday() < 5 and 8 <= now.hour < 18


def decide(db: Session, action_type: str, target: str, params: dict, confidence: float,
           agent_cap: str = "autonomous") -> Decision:
    policy = get_policy(db)
    spec = ACTIONS_BY_TYPE.get(action_type)
    if not spec:
        return Decision(False, reasons=[f"unknown action type '{action_type}'"])
    level = policy.get("autonomy_level", "recommend")
    if level == "observe":
        return Decision(False, reasons=["autonomy level is 'observe': agents may not propose actions"])

    rule = next((r for r in policy["action_rules"] if r["type"] == action_type), None) or {}
    if not rule.get("enabled", True):
        return Decision(False, reasons=[f"action '{action_type}' is disabled by policy"])
    hit = protected_hit(policy, action_type, target, params)
    if hit:
        return Decision(False, reasons=[hit])

    rule_level = rule.get("autonomy", "inherit")
    mode = LEVEL_TO_MODE.get(level, "manual") if rule_level == "inherit" else rule_level
    if mode not in MODE_RANK:
        mode = "manual"
    cap_mode = LEVEL_TO_MODE.get(agent_cap, "manual") if agent_cap != "observe" else "manual"
    reasons: list[str] = []
    if MODE_RANK[cap_mode] < MODE_RANK[mode]:
        mode = cap_mode
        reasons.append(f"agent autonomy capped at '{agent_cap}'")

    if mode == "autonomous":
        demote = []
        if spec["risk"] == "critical":
            demote.append("critical-risk actions always need a human")
        if confidence < float(rule.get("min_confidence", 0.9)):
            demote.append(f"confidence {confidence:.2f} below {rule.get('min_confidence')}")
        since = utcnow() - timedelta(hours=1)
        recent = db.query(Action).filter(Action.type == action_type, Action.auto_approved.is_(True),
                                         Action.created_at >= since).count()
        if recent >= int(rule.get("max_per_hour", 10)):
            demote.append(f"hourly auto-execution budget ({rule.get('max_per_hour')}) exhausted")
        if policy.get("business_hours_only") and not _business_hours(utcnow()):
            demote.append("outside business hours")
        if demote:
            mode = "supervised"
            reasons += demote
        else:
            reasons.append("eligible for autonomous execution")
    return Decision(True, mode=mode, reasons=reasons)
