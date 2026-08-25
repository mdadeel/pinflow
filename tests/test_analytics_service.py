from datetime import timedelta

import pytest

METRICS = {"impressions": 1000, "clicks": 50, "saves": 20, "outbound_clicks": 7}


@pytest.fixture
def db(tmp_path):
    from pinterest_automation.database.db import make_session_factory
    return make_session_factory(f"sqlite:///{tmp_path}/t.db")


def _published_pin(db, **kw):
    from pinterest_automation.database.db import utcnow
    from pinterest_automation.database.models import Pin
    with db() as s:
        p = Pin(image_path="/i.png", image_hash=f"h{kw.get('tag','')}",
                status="published", pin_id_str=kw.get("pin_id_str", "p1"),
                published_time=utcnow() - timedelta(days=5))
        s.add(p)
        s.commit()
        return p.id


def test_sync_upserts_and_computes_ctr(db, monkeypatch):
    from pinterest_automation.database.models import AnalyticsRow
    from pinterest_automation.services import analytics_service as svc
    pid = _published_pin(db)
    fetched = []

    def fake_metrics(pin_id, start, end, token=None):
        fetched.append((pin_id, start, end))
        return METRICS

    monkeypatch.setattr(svc, "get_pin_analytics", fake_metrics)
    n = svc.sync_published(db(), token="t")
    assert n == 1 and fetched[0][0] == "p1"
    with db() as s:
        row = s.query(AnalyticsRow).one()
        assert row.impressions == 1000 and abs(row.ctr - 0.05) < 1e-9


def test_second_sync_updates_not_duplicates(db, monkeypatch):
    from pinterest_automation.database.models import AnalyticsRow
    from pinterest_automation.services import analytics_service as svc
    _published_pin(db)
    monkeypatch.setattr(svc, "get_pin_analytics", lambda *a, **k: dict(METRICS, impressions=2000))
    svc.sync_published(db())
    svc.sync_published(db())
    with db() as s:
        rows = s.query(AnalyticsRow).all()
        assert len(rows) == 1 and rows[0].impressions == 2000


def test_zero_impressions_ctr_is_zero(db, monkeypatch):
    from pinterest_automation.database.models import AnalyticsRow
    from pinterest_automation.services import analytics_service as svc
    _published_pin(db)
    monkeypatch.setattr(svc, "get_pin_analytics",
                        lambda *a, **k: {"impressions": 0, "clicks": 0, "saves": 0, "outbound_clicks": 0})
    svc.sync_published(db())
    with db() as s:
        assert s.query(AnalyticsRow).one().ctr == 0.0


def test_fetch_failure_continues(db, monkeypatch):
    from pinterest_automation.services import analytics_service as svc
    _published_pin(db, tag="ok", pin_id_str="pok")
    _published_pin(db, tag="bad", pin_id_str="pbad")
    calls = []

    def flaky(pin_id, *a, **k):
        calls.append(pin_id)
        if pin_id == "pbad":
            raise RuntimeError("api down")
        return METRICS

    monkeypatch.setattr(svc, "get_pin_analytics", flaky)
    n = svc.sync_published(db())
    assert n == 1 and sorted(calls) == ["pbad", "pok"]


def test_skips_unpublished_and_old(db, monkeypatch):
    from datetime import timedelta
    from pinterest_automation.database.db import utcnow
    from pinterest_automation.database.models import Pin
    from pinterest_automation.services import analytics_service as svc
    with db() as s:
        s.add(Pin(image_path="/a.png", image_hash="ha", status="pending"))           # unpublished
        s.add(Pin(image_path="/b.png", image_hash="hb", status="published",
                  pin_id_str="old", published_time=utcnow() - timedelta(days=60)))   # outside lookback
        s.add(Pin(image_path="/c.png", image_hash="hc", status="published"))         # no pin_id_str
        s.commit()
    assert svc.sync_published(db()) == 0
