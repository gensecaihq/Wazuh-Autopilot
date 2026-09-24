"""In-process pub/sub for Server-Sent Events.

Agents run in worker threads; publish() is thread-safe and hands events to the
asyncio loop that serves SSE subscribers.
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Any

log = logging.getLogger(__name__)


def _default(o: Any):
    if isinstance(o, datetime):
        return o.isoformat()
    return str(o)


class EventBus:
    def __init__(self) -> None:
        self._subscribers: set[asyncio.Queue] = set()
        self._loop: asyncio.AbstractEventLoop | None = None

    def bind_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=1000)
        self._subscribers.add(q)
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        self._subscribers.discard(q)

    def _fanout(self, message: str) -> None:
        for q in list(self._subscribers):
            try:
                q.put_nowait(message)
            except asyncio.QueueFull:
                pass  # slow client; drop rather than block the swarm

    def publish(self, event_type: str, data: dict) -> None:
        if not self._loop or not self._subscribers:
            return
        message = f"event: {event_type}\ndata: {json.dumps(data, default=_default)}\n\n"
        try:
            self._loop.call_soon_threadsafe(self._fanout, message)
        except RuntimeError:
            log.debug("event loop closed; dropping %s", event_type)


bus = EventBus()
