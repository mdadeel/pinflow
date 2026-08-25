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


def test_stats_counts_and_empty_analytics(env):
    f, c = env
    from pinterest_automation.database.models import Pin

    with f() as s:
        for i, status in enumerate(["pending", "pending", "ready",
                                    "scheduled", "published", "failed"]):
            s.add(Pin(image_path=f"/{i}.png", image_hash=f"h{i}", status=status))
        s.commit()
    body = c.get("/api/stats").json()
    assert body["total"] == 6
    assert body["pending"] == 2 and body["ready"] == 1
    assert body["scheduled"] == 1 and body["published"] == 1 and body["failed"] == 1
    assert body["impressions"] == 0 and body["clicks"] == 0


def test_stats_sums_analytics(env):
    f, c = env
    from pinterest_automation.database.models import AnalyticsRow, Pin

    with f() as s:
        p = Pin(image_path="/a.png", image_hash="h1", status="published")
        s.add(p)
        s.commit()
        s.add(AnalyticsRow(pin_id=p.id, impressions=1200, clicks=34,
                           saves=7, outbound_clicks=2))
        s.commit()
    body = c.get("/api/stats").json()
    assert (body["impressions"], body["clicks"], body["saves"], body["outbound_clicks"]) == (1200, 34, 7, 2)


def test_stats_empty_db(env):
    f, c = env
    body = c.get("/api/stats").json()
    assert body["total"] == 0 and all(body[k] == 0 for k in
        ("pending", "ready", "scheduled", "published", "failed", "impressions"))
