import json
import pytest
from datetime import datetime, timezone

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


def test_delete_pin_204(env):
    f, c = env
    pid = _add_pin(f, image_hash="h1")
    r = c.delete(f"/api/pins/{pid}")
    assert r.status_code == 204
    assert c.get(f"/api/pins/{pid}").status_code == 404


def test_reset_pin_clears_metadata_and_status(env):
    f, c = env
    pid = _add_pin(
        f,
        image_hash="h1",
        status="scheduled",
        scheduled_time=datetime(2026, 1, 1, tzinfo=timezone.utc),
        title="T",
        description="D",
        primary_keyword="k",
        secondary_keywords=json.dumps(["a"]),
        tags=json.dumps(["t"]),
        board_name="B",
        retry_count=3,
        error_message="boom",
    )
    r = c.post(f"/api/pins/{pid}/reset")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "pending"
    assert body["scheduled_time"] is None
    assert body["title"] is None
    assert body["secondary_keywords"] is None
    assert body["tags"] is None
    assert body["board_name"] is None


def test_reset_missing_pin_404(env):
    f, c = env
    assert c.post("/api/pins/999999/reset").status_code == 404


def test_retry_publish_failure_resets(env, monkeypatch):
    import pinterest_automation.services.pin_actions as pa

    def fake_publish(*args):
        raise RuntimeError("publish boom")

    monkeypatch.setattr(pa, "_publish_now", fake_publish)
    f, c = env
    pid = _add_pin(f, image_hash="h1", status="scheduled")
    r = c.post(f"/api/pins/{pid}/retry")
    assert r.status_code == 200
    assert c.get(f"/api/pins/{pid}").json()["status"] == "pending"


def test_retry_ready_schedules(env, monkeypatch):
    import pinterest_automation.services.pin_actions as pa
    from pinterest_automation.database import db as dbmod
    from pinterest_automation.database.models import Pin

    def fake_schedule(db, ids):
        with dbmod.get_session_factory()() as s:
            for pid in ids:
                p = s.get(Pin, pid)
                p.status = "scheduled"
                s.commit()

    monkeypatch.setattr(pa.scheduler, "assign_schedule_times", fake_schedule)
    f, c = env
    pid = _add_pin(f, image_hash="h1", status="ready")
    r = c.post(f"/api/pins/{pid}/retry")
    assert r.status_code == 200
    assert c.get(f"/api/pins/{pid}").json()["status"] == "scheduled"


def test_bulk_reset_all(env):
    f, c = env
    _add_pin(f, image_hash="a", status="scheduled", title="T1")
    _add_pin(f, image_hash="b", status="scheduled", title="T2")
    r = c.post("/api/pins/bulk", json={"action": "reset"})
    assert r.status_code == 200
    assert r.json()["processed"] == 2
    assert all(p["status"] == "pending" for p in c.get("/api/pins").json()["items"])


def test_bulk_delete_specific_ids(env):
    f, c = env
    p1 = _add_pin(f, image_hash="a")
    p2 = _add_pin(f, image_hash="b")
    r = c.post("/api/pins/bulk", json={"action": "delete", "ids": [p1]})
    assert r.status_code == 200
    assert c.get(f"/api/pins/{p1}").status_code == 404
    assert c.get(f"/api/pins/{p2}").status_code == 200
