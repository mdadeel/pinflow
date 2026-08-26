import threading
import time

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path, monkeypatch):
    from pinterest_automation.api import rest, ws as wsmod
    from pinterest_automation.database import db as dbmod

    f = dbmod.make_session_factory(f"sqlite:///{tmp_path}/t.db")
    monkeypatch.setattr(dbmod, "get_session_factory", lambda: f)
    app = FastAPI()
    app.include_router(rest.router)
    app.include_router(wsmod.router)
    return TestClient(app)


def test_hello_contains_recent_events(client):
    from pinterest_automation.services import events

    events.publish("image.uploaded", path="/seed.png", filename="seed.png")
    with client.websocket_connect("/ws") as ws:
        hello = ws.receive_json()
        assert hello["type"] == "hello"
        types = [e["type"] for e in hello["payload"]["recent"]]
        assert "image.uploaded" in types


def test_live_event_reaches_connected_client(client):
    from pinterest_automation.services import events

    with client.websocket_connect("/ws") as ws:
        ws.receive_json()                       # consume hello
        events.publish("pin.published", pin_id=1, pin_url="u")
        msg = ws.receive_json()
        assert msg["type"] == "pin.published"
        assert msg["payload"]["pin_id"] == 1


def test_cors_allows_local_frontend(client):
    from pinterest_automation.dashboard.app import app as real_app

    r = TestClient(real_app).options(
        "/api/stats",
        headers={"Origin": "http://localhost:3000",
                 "Access-Control-Request-Method": "GET"})
    assert r.status_code in (200, 400)          # preflight handled by middleware
    assert r.headers.get("access-control-allow-origin") == "http://localhost:3000"


def test_disconnect_unsubscribes(client):
    from pinterest_automation.services import events

    before = len(events._subs)
    with client.websocket_connect("/ws"):
        pass                                    # connect then immediately close
    deadline = time.time() + 2
    while len(events._subs) > before and time.time() < deadline:
        time.sleep(0.05)
    assert len(events._subs) == before          # no leaked subscriptions
