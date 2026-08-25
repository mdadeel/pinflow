import json
from datetime import date, datetime, time, timedelta, timezone

import pytest


@pytest.fixture
def db(tmp_path, monkeypatch):
    from pinterest_automation.config import settings as cfgmod
    monkeypatch.setattr(cfgmod.settings, "reports_dir", tmp_path / "reports")
    from pinterest_automation.database.db import make_session_factory
    return make_session_factory(f"sqlite:///{tmp_path}/t.db")


def _seed(db, day):
    """2 published pins today w/ analytics, 1 failed pin today."""
    from pinterest_automation.database.models import AnalyticsRow, Pin
    day_start = datetime(day.year, day.month, day.day, tzinfo=timezone.utc)
    with db() as s:
        for i in range(2):
            p = Pin(image_path=f"/{i}.png", image_hash=f"h{i}", status="published",
                    content_category="Anime", primary_keyword="anime wallpaper",
                    board_name="Anime Board", published_time=day_start)
            s.add(p)
        s.add(Pin(image_path="/f.png", image_hash="hf", status="failed",
                  error_message="x"))
        s.commit()
        for p in s.query(Pin).filter(Pin.status == "published"):
            s.add(AnalyticsRow(pin_id=p.id, impressions=500, clicks=10,
                               saves=2, outbound_clicks=1))
        s.commit()


def test_daily_report_counts(db):
    from pinterest_automation.services.reporting import daily_report
    day = date.today()
    _seed(db, day)
    with db() as s:
        rep = daily_report(s, day)
    assert rep["date"] == day.isoformat()
    assert rep["pins_posted"] == 2
    assert rep["pins_failed"] == 1
    assert rep["ai_calls"] == 0          # nothing analyzed in fixture


def test_weekly_report_ranks_by_clicks(db):
    from pinterest_automation.services.reporting import weekly_report
    _seed(db, date.today())
    with db() as s:
        rep = weekly_report(s, date.today())
    assert rep["top_categories"][0]["category"] == "Anime"
    assert rep["top_categories"][0]["clicks"] == 20      # 10 x 2 pins summed
    assert rep["top_categories"][0]["impressions"] == 1000
    assert rep["best_keywords"][0]["keyword"] == "anime wallpaper"
    assert rep["best_boards"][0]["board_name"] == "Anime Board"


def test_weekly_skips_null_group_keys(db):
    from pinterest_automation.database.models import AnalyticsRow, Pin
    from pinterest_automation.services.reporting import weekly_report
    from pinterest_automation.database.db import utcnow
    with db() as s:
        p = Pin(image_path="/n.png", image_hash="hn", status="published",
                content_category=None, primary_keyword=None, board_name=None,
                published_time=utcnow())
        s.add(p)
        s.commit()
        s.add(AnalyticsRow(pin_id=p.id, impressions=10, clicks=5))
        s.commit()
        rep = weekly_report(s, date.today())
    assert all(r["category"] is not None for r in rep["top_categories"])
    assert all(r["keyword"] is not None for r in rep["best_keywords"])
    assert all(r["board_name"] is not None for r in rep["best_boards"])


def test_weekly_excludes_out_of_window(db):
    from pinterest_automation.database.models import AnalyticsRow, Pin
    from pinterest_automation.services.reporting import weekly_report
    day_start = datetime.combine(date.today(), time.min, tzinfo=timezone.utc)
    with db() as s:
        s.add(Pin(image_path="/old.png", image_hash="hold", status="published",
                  content_category="OldCat", primary_keyword="old kw",
                  board_name="Old Board",
                  published_time=day_start - timedelta(days=10)))
        s.add(Pin(image_path="/fut.png", image_hash="hfut", status="scheduled",
                  content_category="FutureCat", primary_keyword="future kw",
                  board_name="Future Board",
                  published_time=day_start + timedelta(days=1)))
        s.commit()
        for p in s.query(Pin):
            s.add(AnalyticsRow(pin_id=p.id, impressions=999, clicks=99))
        s.commit()
    with db() as s:
        rep = weekly_report(s, date.today())
    assert rep["top_categories"] == []
    assert rep["best_keywords"] == []
    assert rep["best_boards"] == []


def test_write_report_file(db):
    from pinterest_automation.services.reporting import write_report
    path = write_report({"date": "2026-08-25", "pins_posted": 1}, "daily")
    assert path.exists()
    assert json.loads(path.read_text())["pins_posted"] == 1
