import logging
import queue
import threading
from collections import deque

from pinterest_automation.database.db import utcnow

log = logging.getLogger(__name__)
_subs: list = []
_lock = threading.Lock()
_recent: deque = deque(maxlen=200)


def subscribe():
    q = queue.Queue()
    with _lock:
        _subs.append(q)
    return q


def unsubscribe(q) -> None:
    with _lock:
        if q in _subs:
            _subs.remove(q)


def recent_events(limit: int = 50) -> list:
    with _lock:
        return list(_recent)[-limit:]


def publish(event_type: str, **payload) -> dict:
    """Fire-and-forget activity event. Safe from any thread; never raises."""
    evt = {"type": event_type, "payload": payload, "at": utcnow().isoformat()}
    with _lock:
        _recent.append(evt)
        subs = list(_subs)
    for q in subs:
        try:
            q.put_nowait(evt)
        except Exception:  # noqa: BLE001 - dead subscriber must not break publishers
            log.warning("event subscriber dropped")
    log.info("event %s %s", event_type, payload)
    return evt
