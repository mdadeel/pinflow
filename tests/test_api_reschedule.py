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


def test_reschedule_ready_pin(env):
    f, c = env
    pid = _add_pin(f, image_hash="h1", status="ready")
    r = c.patch(f"/api/pins/{pid}/schedule",
                json={"scheduled_time": "2026-09-01T14:00:00"})
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "scheduled"
    assert body["scheduled_time"].startswith("2026-09-01T14:00:00")


def test_reschedule_published_pin_409(env):
    f, c = env
    pid = _add_pin(f, image_hash="h1", status="published")
    r = c.patch(f"/api/pins/{pid}/schedule",
                json={"scheduled_time": "2026-09-01T14:00:00"})
    assert r.status_code == 409
    assert "pin is published" in r.json()["detail"]


def test_reschedule_unknown_pin_404(env):
    f, c = env
    r = c.patch("/api/pins/999999/schedule",
                json={"scheduled_time": "2026-09-01T14:00:00"})
    assert r.status_code == 404


def test_reschedule_emits_pin_scheduled(env):
    f, c = env
    from pinterest_automation.services import events

    pid = _add_pin(f, image_hash="h1", status="ready")
    q = events.subscribe()
    try:
        c.patch(f"/api/pins/{pid}/schedule",
                json={"scheduled_time": "2026-09-01T14:00:00"})
        seen = []
        while not q.empty():
            seen.append(q.get_nowait())
    finally:
        events.unsubscribe(q)
    evt = next(e for e in seen if e["type"] == "pin.scheduled")
    assert evt["payload"]["pin_id"] == pid
