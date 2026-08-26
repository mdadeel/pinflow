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


def _add_analytics(f, pin_id, impressions=0, saves=0, clicks=0, days_ago=0):
    from datetime import timedelta

    from pinterest_automation.database.models import AnalyticsRow
    from pinterest_automation.database.db import utcnow

    with f() as s:
        row = AnalyticsRow(
            pin_id=pin_id, impressions=impressions, saves=saves, clicks=clicks,
            last_updated=utcnow() - timedelta(days=days_ago),
        )
        s.add(row)
        s.commit()


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
    assert all(set(e.keys()) >= {"date", "published", "clicks", "impressions"}
               for e in body["series"])


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


def test_analytics_top_pins_and_ctr(env):
    f, c = env
    p1 = _add_pin(f, image_hash="h1", title="Pin A")
    p2 = _add_pin(f, image_hash="h2", title="Pin B")
    p3 = _add_pin(f, image_hash="h3", title="Pin C")
    _add_analytics(f, p1, impressions=100, saves=10, clicks=5)   # ctr 0.05
    _add_analytics(f, p2, impressions=200, saves=20, clicks=40)  # ctr 0.20
    _add_analytics(f, p3, impressions=300, saves=0, clicks=0)    # ctr 0.0

    body = c.get("/api/analytics").json()
    top = body["top_pins"]
    assert len(top) == 3
    # ordered by clicks desc: p2(40), p1(5), p3(0)
    assert top[0]["id"] == p2
    assert top[0]["title"] == "Pin B"
    assert top[0]["clicks"] == 40
    assert top[0]["impressions"] == 200
    assert top[0]["saves"] == 20
    assert top[1]["id"] == p1 and top[1]["title"] == "Pin A"
    assert top[2]["id"] == p3 and top[2]["title"] == "Pin C"
    # ctr = total clicks / total impressions = 45 / 600 = 0.075
    assert body["ctr"] == pytest.approx(45 / 600)


def test_analytics_series_includes_clicks(env):
    f, c = env
    from pinterest_automation.database.db import utcnow

    p1 = _add_pin(f, image_hash="h1", status="published", published_time=utcnow())
    _add_analytics(f, p1, impressions=100, clicks=7)

    body = c.get("/api/analytics").json()
    today = utcnow().date().isoformat()
    entry = next(e for e in body["series"] if e["date"] == today)
    assert entry["clicks"] == 7
    assert entry["impressions"] == 100
    assert entry["published"] == 1
