"""Best-effort Slack notifications (incoming webhook)."""

import logging
import threading

import httpx

from .db import session_scope
from .settings_store import get_section

log = logging.getLogger(__name__)


def send_slack(url: str, text: str) -> tuple[bool, str | None]:
    try:
        r = httpx.post(url, json={"text": text}, timeout=10)
        return r.is_success, None if r.is_success else f"HTTP {r.status_code}"
    except httpx.HTTPError as e:
        return False, str(e)


def notify(event: str, text: str) -> None:
    try:
        with session_scope() as db:
            cfg = get_section(db, "notifications")
    except Exception:
        return
    url = cfg.get("slack_webhook_url")
    if not url or event not in (cfg.get("notify_on") or []):
        return
    threading.Thread(target=send_slack, args=(url, text), daemon=True).start()
