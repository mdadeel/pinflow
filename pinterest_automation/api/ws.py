import asyncio
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from pinterest_automation.services import events

log = logging.getLogger(__name__)
router = APIRouter()


@router.websocket("/ws")
async def event_stream(ws: WebSocket):
    await ws.accept()
    q = events.subscribe()
    try:
        await ws.send_json({"type": "hello",
                            "payload": {"recent": events.recent_events(limit=50)}})
        loop = asyncio.get_running_loop()
        while True:
            # blocking queue.get offloaded to a thread; 1s timeout keeps us
            # responsive to client disconnects
            evt = await loop.run_in_executor(None, lambda: _get_or_none(q))
            if evt is None:
                if ws.client_state.name != "CONNECTED":
                    break
                continue
            await ws.send_json(evt)
    except WebSocketDisconnect:
        pass
    except Exception as e:  # noqa: BLE001 - transport gone; normal lifecycle noise
        log.debug("ws closed: %s", e)
    finally:
        events.unsubscribe(q)


def _get_or_none(q, timeout: float = 1.0):
    try:
        return q.get(timeout=timeout)
    except Exception:  # queue.Empty
        return None
