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


def test_post_records_signal_and_get_returns_it(env):
    f, c = env
    r = c.post("/api/learning", json={"action": "approved", "pin_id": 7})
    assert r.status_code == 201
    body = r.json()
    assert body["action"] == "approved" and body["pin_id"] == 7 and body["id"]

    g = c.get("/api/learning").json()
    assert g["counts"] == {"approved": 1}
    assert g["total"] == 1


def test_multiple_actions_aggregate_correctly(env):
    f, c = env
    for a in ("approved", "rejected", "approved", "regenerated", "approved", "rejected"):
        c.post("/api/learning", json={"action": a})
    g = c.get("/api/learning").json()
    assert g["counts"] == {"approved": 3, "rejected": 2, "regenerated": 1}
    assert g["total"] == 6


def test_pin_id_is_stored_and_echoed(env):
    f, c = env
    r = c.post("/api/learning", json={"action": "edited", "pin_id": 42})
    assert r.status_code == 201
    assert r.json()["pin_id"] == 42

    r2 = c.post("/api/learning", json={"action": "published"})
    assert r2.json()["pin_id"] is None
