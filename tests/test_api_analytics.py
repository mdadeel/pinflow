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


def test_analytics_totals_and_by_status(env):
    f, c = env
    _add_pin(f, image_hash="h1", status="pending")
    _add_pin(f, image_hash="h2", status="ready")
    _add_pin(f, image_hash="h3", status="scheduled")
    _add_pin(f, image_hash="h4", status="published")
    _add_pin(f, image_hash="h5", status="published")
    _add_pin(f, image_hash="h6", status="failed")
    body = c.get("/api/analytics").json()
    assert body["totals"]["pins"] == 6
    assert body["totals"]["pending"] == 1
    assert body["totals"]["ready"] == 1
    assert body["totals"]["scheduled"] == 1
    assert body["totals"]["published"] == 2
    assert body["totals"]["failed"] == 1
    assert body["by_status"] == {"pending": 1, "ready": 1,
                                 "scheduled": 1, "published": 2, "failed": 1}


def test_analytics_series_has_30_entries(env):
    f, c = env
    body = c.get("/api/analytics").json()
    assert len(body["series"]) == 30
    dates = [e["date"] for e in body["series"]]
    assert len(set(dates)) == 30
    assert all(set(e.keys()) == {"date", "published"} for e in body["series"])


def test_analytics_series_counts_published_today(env):
    f, c = env
    from pinterest_automation.database.db import utcnow

    now = utcnow()
    _add_pin(f, image_hash="h1", status="published", published_time=now)
    body = c.get("/api/analytics").json()
    entry = next(e for e in body["series"] if e["date"] == now.date().isoformat())
    assert entry["published"] == 1


def test_analytics_top_pins_empty_and_ctr_zero(env):
    f, c = env
    body = c.get("/api/analytics").json()
    assert body["top_pins"] == []
    assert body["ctr"] == 0.0
