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


def test_edit_round_trips(env):
    f, c = env
    pid = _add_pin(f, image_hash="h1")
    r = c.patch(f"/api/pins/{pid}", json={
        "title": "New Title",
        "description": "New desc",
        "board_name": "My Board",
        "secondary_keywords": ["a", "b"],
        "tags": ["t"],
    })
    assert r.status_code == 200
    body = r.json()
    assert body["title"] == "New Title"
    assert body["description"] == "New desc"
    assert body["board_name"] == "My Board"
    assert body["secondary_keywords"] == ["a", "b"]
    assert body["tags"] == ["t"]

    got = c.get(f"/api/pins/{pid}").json()
    assert got["title"] == "New Title"
    assert got["secondary_keywords"] == ["a", "b"]
    assert got["tags"] == ["t"]


def test_edit_published_pin_409(env):
    f, c = env
    pid = _add_pin(f, image_hash="h1", status="published")
    r = c.patch(f"/api/pins/{pid}", json={"title": "x"})
    assert r.status_code == 409
    assert "not editable" in r.json()["detail"]


def test_edit_missing_pin_404(env):
    f, c = env
    r = c.patch("/api/pins/999999", json={"title": "x"})
    assert r.status_code == 404


def test_schedule_publish_times_in_pinout(env):
    f, c = env
    pid = _add_pin(f, image_hash="h1",
                   scheduled_time=datetime(2026, 1, 1, tzinfo=timezone.utc))
    got = c.get(f"/api/pins/{pid}").json()
    assert isinstance(got["scheduled_time"], str)
    assert got["scheduled_time"].endswith("2026-01-01T00:00:00")
    assert got["published_time"] is None
