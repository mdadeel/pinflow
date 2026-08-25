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


def test_list_returns_pinouts_newest_first(env):
    f, c = env
    ids = [_add_pin(f, image_hash=f"h{i}", title=f"Pin {i}") for i in range(3)]
    r = c.get("/api/pins")
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 3 and len(body["items"]) == 3
    assert [i["id"] for i in body["items"]] == list(reversed(ids))   # newest first


def test_list_filters_and_searches(env):
    f, c = env
    _add_pin(f, image_hash="h1", status="ready", board_name="Anime Board")
    _add_pin(f, image_hash="h2", status="pending", title="sunset vibes")
    assert c.get("/api/pins?status=ready").json()["total"] == 1
    assert c.get("/api/pins?q=sunset").json()["total"] == 1
    assert c.get("/api/pins?q=anime").json()["total"] == 1           # matches board_name
    assert c.get("/api/pins?q=nomatch").json()["total"] == 0


def test_list_pagination(env):
    f, c = env
    for i in range(5):
        _add_pin(f, image_hash=f"h{i}")
    body = c.get("/api/pins?page=2&per_page=2").json()
    assert body["page"] == 2 and body["per_page"] == 2 and body["total"] == 5
    assert len(body["items"]) == 2


def test_get_detail_404(env):
    f, c = env
    pid = _add_pin(f, image_hash="h1", status="ready")
    assert c.get(f"/api/pins/{pid}").status_code == 200
    assert c.get("/api/pins/999999").status_code == 404


def test_manual_move_pending_to_ready_and_back(env):
    f, c = env
    pid = _add_pin(f, image_hash="h1")
    r = c.patch(f"/api/pins/{pid}/status", json={"status": "ready"})
    assert r.status_code == 200 and r.json()["status"] == "ready"
    r = c.patch(f"/api/pins/{pid}/status", json={"status": "pending"})
    assert r.status_code == 200 and r.json()["status"] == "pending"


def test_manual_move_to_pipeline_status_rejected(env):
    f, c = env
    pid = _add_pin(f, image_hash="h1")
    for target in ("scheduled", "published", "failed"):
        r = c.patch(f"/api/pins/{pid}/status", json={"status": target})
        assert r.status_code == 409, target


def test_move_unknown_status_422_missing_pin_404(env):
    f, c = env
    pid = _add_pin(f, image_hash="h1")
    assert c.patch(f"/api/pins/{pid}/status", json={"status": "bogus"}).status_code == 422
    assert c.patch("/api/pins/999999/status", json={"status": "ready"}).status_code == 404


def test_move_emits_pin_updated(env):
    f, c = env
    from pinterest_automation.services import events

    pid = _add_pin(f, image_hash="h1")
    q = events.subscribe()
    try:
        c.patch(f"/api/pins/{pid}/status", json={"status": "ready"})
        seen = []
        while not q.empty():
            seen.append(q.get_nowait())
    finally:
        events.unsubscribe(q)
    evt = next(e for e in seen if e["type"] == "pin.updated")
    assert evt["payload"] == {"pin_id": pid, "status": "ready"}
