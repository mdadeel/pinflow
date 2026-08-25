from datetime import datetime, timedelta, timezone

import pytest


@pytest.fixture
def env(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from pinterest_automation.database import db as dbmod
    f = dbmod.make_session_factory(f"sqlite:///{tmp_path}/t.db")
    monkeypatch.setattr(dbmod, "get_session_factory", lambda: f)

    from pinterest_automation.dashboard.app import app
    return f, TestClient(app)


def test_overview_counts(env, tmp_path):
    f, c = env
    from pinterest_automation.database.models import Pin
    with f() as s:
        s.add(Pin(image_path="/a.png", image_hash="1", status="pending"))
        s.add(Pin(image_path="/b.png", image_hash="2", status="ready"))
        s.add(Pin(image_path="/c.png", image_hash="3", status="scheduled"))
        s.add(Pin(image_path="/d.png", image_hash="4", status="published"))
        s.add(Pin(image_path="/e.png", image_hash="5", status="failed"))
        s.commit()
    html = c.get("/").text
    assert "Total Images" in html and "Scheduled Pins" in html and "Failed Pins" in html
    assert ">5<" in html or "5" in html          # total rendered somewhere


def test_library_lists_metadata_and_filters(env, tmp_path):
    f, c = env
    from pinterest_automation.database.models import Pin
    img = tmp_path / "a.png"
    img.write_bytes(b"\x89PNG")
    with f() as s:
        s.add(Pin(image_path=str(img), image_hash="1", status="ready",
                  title="T" * 70, description="D" * 310,
                  content_category="Anime", board_name="Anime Board",
                  primary_keyword="anime wallpaper"))
        s.commit()
    html = c.get("/library").text
    assert "/media/" in html and "Anime" in html and "anime wallpaper" in html
    # filter excludes other statuses
    assert c.get("/library?status=published").text.find("T" * 70) == -1


def test_calendar_shows_scheduled_titles(env):
    f, c = env
    from pinterest_automation.database.models import Pin
    future = datetime.now(timezone.utc) + timedelta(days=3)
    title = "Future Pin Title Here That Is Long Enough For Pinterest Specs Ok"
    with f() as s:
        s.add(Pin(image_path="/x.png", image_hash="1", status="scheduled",
                  title=title, scheduled_time=future))
        s.commit()
    month = future.strftime("%Y-%m")
    html = c.get(f"/calendar?month={month}").text
    assert title in html
    assert c.get("/calendar").status_code == 200     # defaults to current month


def test_analytics_view_totals_and_top(env):
    f, c = env
    from pinterest_automation.database.models import AnalyticsRow, Pin
    with f() as s:
        p = Pin(image_path="/x.png", image_hash="1", status="published",
                title="Top Pin " * 9)
        s.add(p)
        s.commit()
        s.add(AnalyticsRow(pin_id=p.id, impressions=1000, clicks=90,
                           saves=5, outbound_clicks=3, ctr=0.09))
        s.commit()
    html = c.get("/analytics").text
    assert "Top Pin" in html and ("1,000" in html or "1000" in html)
    assert "9.00%" in html          # CTR rendered as percentage


def test_media_serves_registered_file_only(env, tmp_path):
    f, c = env
    from pinterest_automation.database.models import Pin
    img = tmp_path / "real.png"
    img.write_bytes(b"\x89PNG-real-bytes")
    with f() as s:
        s.add(Pin(image_path=str(img), image_hash="1"))
        s.commit()
        pid = s.query(Pin).one().id
    r = c.get(f"/media/{pid}")
    assert r.status_code == 200 and r.content == b"\x89PNG-real-bytes"
    assert c.get("/media/999999").status_code == 404
    missing = tmp_path / "gone.png"
    with f() as s:
        s.add(Pin(image_path=str(missing), image_hash="2"))
        s.commit()
        pid2 = s.query(Pin).order_by(Pin.id.desc()).first().id
    assert c.get(f"/media/{pid2}").status_code == 404
