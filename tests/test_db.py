import pytest
from sqlalchemy.exc import IntegrityError

from datetime import datetime, timedelta, timezone


@pytest.fixture
def Session(tmp_path):
    from pinterest_automation.database.db import make_session_factory
    return make_session_factory(f"sqlite:///{tmp_path}/t.db")


def test_pin_roundtrip(Session):
    from pinterest_automation.database.models import Pin
    with Session() as db:
        db.add(Pin(image_path="/a.png", image_hash="h1"))
        db.commit()
        p = db.query(Pin).one()
        assert p.status == "pending"
        assert p.retry_count == 0
        assert p.created_at is not None


def test_duplicate_hash_rejected(Session):
    from pinterest_automation.database.models import Pin
    with Session() as db:
        db.add(Pin(image_path="/a.png", image_hash="h1")); db.commit()
        db.add(Pin(image_path="/b.png", image_hash="h1"))
        with pytest.raises(IntegrityError):
            db.commit()


def test_analytics_fk(Session):
    from pinterest_automation.database.models import Pin, AnalyticsRow
    with Session() as s:
        p = Pin(image_path="/a.png", image_hash="h1"); s.add(p); s.commit()
        s.add(AnalyticsRow(pin_id=p.id, impressions=10, clicks=1)); s.commit()
        row = s.query(AnalyticsRow).one()
        assert row.pin_id == p.id and row.ctr >= 0


def test_invalid_fk_rejected(Session):
    from pinterest_automation.database.models import AnalyticsRow
    with Session() as s:
        s.add(AnalyticsRow(pin_id=99999))
        with pytest.raises(IntegrityError):
            s.commit()


def test_duplicate_analytics_row_rejected(Session):
    from pinterest_automation.database.models import Pin, AnalyticsRow
    with Session() as s:
        p = Pin(image_path="/a.png", image_hash="h1"); s.add(p); s.commit()
        s.add(AnalyticsRow(pin_id=p.id)); s.commit()
        s.add(AnalyticsRow(pin_id=p.id))
        with pytest.raises(IntegrityError):
            s.commit()


def test_naive_datetime_assumed_utc(Session):
    from pinterest_automation.database.models import Pin
    with Session() as db:
        db.add(Pin(image_path="/a.png", image_hash="h1",
                   scheduled_time=datetime(2026, 1, 1, 12, 0)))
        db.commit()
        p = db.query(Pin).one()
        assert p.scheduled_time.tzinfo is not None
        assert p.scheduled_time.utcoffset() == timedelta(0)


def test_non_utc_normalized_to_utc(Session):
    from pinterest_automation.database.models import Pin
    tz = timezone(timedelta(hours=2))
    with Session() as db:
        db.add(Pin(image_path="/a.png", image_hash="h1",
                   scheduled_time=datetime(2026, 1, 1, 12, 0, tzinfo=tz)))
        db.commit()
        p = db.query(Pin).one()
        assert p.scheduled_time.utcoffset() == timedelta(0)
        assert (p.scheduled_time.hour, p.scheduled_time.minute) == (10, 0)
