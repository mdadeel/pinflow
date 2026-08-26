import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


@pytest.fixture
def env(tmp_path, monkeypatch):
    from pinterest_automation.api import rest
    from pinterest_automation.database import db as dbmod

    f = dbmod.make_session_factory(f"sqlite:///{tmp_path}/t.db")
    monkeypatch.setattr(dbmod, "get_session_factory", lambda: f)
    app = FastAPI()
    app.include_router(rest.router)
    return f, TestClient(app)


def _add_pin(f, **kw):
    from pinterest_automation.database.models import Pin

    defaults = dict(image_path="/x.png", image_hash=kw.pop("image_hash"), status="pending")
    defaults.update(kw)
    with f() as s:
        p = Pin(**defaults)
        s.add(p)
        s.commit()
        return p.id


def test_approve_ready_pin_schedules(env):
    f, c = env
    pid = _add_pin(f, image_hash="h1", status="ready")
    r = c.post(f"/api/pins/{pid}/approve")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "scheduled"
    assert isinstance(body["scheduled_time"], str) and body["scheduled_time"]
    with f() as s:
        from pinterest_automation.database.models import Pin
        assert s.get(Pin, pid).status == "scheduled"


def test_approve_pending_pin_rejected(env):
    f, c = env
    pid = _add_pin(f, image_hash="h1", status="pending")
    r = c.post(f"/api/pins/{pid}/approve")
    assert r.status_code == 409
    assert "approve requires ready" in r.json()["detail"]


def test_approve_unknown_pin_404(env):
    f, c = env
    assert c.post("/api/pins/999999/approve").status_code == 404


def test_approve_emits_pin_scheduled(env):
    f, c = env
    from pinterest_automation.services import events

    pid = _add_pin(f, image_hash="h1", status="ready")
    q = events.subscribe()
    try:
        c.post(f"/api/pins/{pid}/approve")
        seen = []
        while not q.empty():
            seen.append(q.get_nowait())
    finally:
        events.unsubscribe(q)
    evt = next(e for e in seen if e["type"] == "pin.scheduled")
    assert evt["payload"]["pin_id"] == pid
