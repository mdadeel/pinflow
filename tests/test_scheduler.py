from datetime import datetime, timedelta, timezone

import pytest


@pytest.fixture
def db(tmp_path):
    from pinterest_automation.database.db import make_session_factory
    return make_session_factory(f"sqlite:///{tmp_path}/t.db")


def _ready_pins(db, n):
    from pinterest_automation.database.models import Pin
    with db() as s:
        for i in range(n):
            s.add(Pin(image_path=f"/i{i}.png", image_hash=f"h{i}", status="ready",
                      title="T", description="D", board_name="Anime Board"))
        s.commit()
        return [p.id for p in s.query(Pin).all()]


def test_assign_spreads_across_slots(db):
    from pinterest_automation.config.settings import Settings
    from pinterest_automation.database.models import Pin
    from pinterest_automation.services.scheduler import assign_schedule_times
    cfg = Settings(_env_file=None, post_hours=[8, 11], posts_per_day=2)
    ids = _ready_pins(db, 4)
    with db() as s:
        n = assign_schedule_times(s, ids, cfg=cfg,
                                  now=datetime(2026, 1, 10, 9, 0, tzinfo=timezone.utc))
        assert n == 4
        times = sorted(p.scheduled_time for p in s.query(Pin).filter(Pin.id.in_(ids)))
        days = {t.date() for t in times}
        assert len(days) == 2                       # 2 slots/day -> spills to next day
        per_day = {}
        for t in times:
            per_day[t.date()] = per_day.get(t.date(), 0) + 1
        assert set(per_day.values()) == {2}
        # first slot must be today at 11:00 (8:00 already passed at now=09:00)
        assert times[0].hour == 11


def test_assign_respects_existing_daily_load(db):
    """A day already holding posts_per_day scheduled pins gets no new slot."""
    from pinterest_automation.config.settings import Settings
    from pinterest_automation.database.models import Pin
    from pinterest_automation.services.scheduler import assign_schedule_times
    cfg = Settings(_env_file=None, post_hours=[8], posts_per_day=1)
    ids = _ready_pins(db, 1)
    with db() as s:
        # pre-existing scheduled pin tomorrow 08:00 consumes that day's only slot
        s.add(Pin(image_path="/pre.png", image_hash="hpre", status="scheduled",
                  title="T", board_name="Anime Board",
                  scheduled_time=datetime(2026, 1, 11, 8, 0)))
        s.commit()
        n = assign_schedule_times(s, ids, cfg=cfg,
                                  now=datetime(2026, 1, 10, 9, 0, tzinfo=timezone.utc))
        assert n == 1
        p = s.get(Pin, ids[0])
        assert p.scheduled_time.date() == datetime(2026, 1, 12).date()   # bumped to Jan 12


def test_assign_skips_already_scheduled_ids(db):
    from pinterest_automation.services.scheduler import assign_schedule_times
    ids = _ready_pins(db, 1)
    with db() as s:
        from pinterest_automation.database.models import Pin
        p = s.get(Pin, ids[0])
        p.status = "scheduled"
        p.scheduled_time = datetime(2026, 1, 10, 20, 0)
        s.commit()
        n = assign_schedule_times(s, ids)
        assert n == 0
        assert s.get(Pin, ids[0]).scheduled_time.replace(tzinfo=None) == datetime(
            2026, 1, 10, 20, 0)


def test_due_pins_only_past(db, tmp_path):
    from pinterest_automation.database.models import Pin
    from pinterest_automation.services.scheduler import due_pins
    ids = _ready_pins(db, 3)
    now = datetime.now(timezone.utc)
    with db() as s:
        for pid, t in zip(ids, [now - timedelta(hours=2), now - timedelta(minutes=1),
                                now + timedelta(days=1)]):
            p = s.get(Pin, pid)
            p.status = "scheduled"
            p.scheduled_time = t
        s.commit()
        due = due_pins(s, now=now)
        assert len(due) == 2
        assert due[0].scheduled_time <= due[1].scheduled_time       # oldest first


def test_run_due_publishes_with_shared_boards(db, monkeypatch, tmp_path):
    from pinterest_automation.database.models import Pin
    from pinterest_automation.services import scheduler
    img = tmp_path / "i.png"
    img.write_bytes(b"x")
    ids = _ready_pins(db, 3)
    fetches = []
    monkeypatch.setattr(scheduler, "get_boards",
                        lambda token=None: fetches.append(1) or [{"id": "b1", "name": "Anime Board"}])

    def fake_publish(db_, pin, token=None, boards=None):
        assert boards is not None          # shared list passed down
        pin.status = "published"
        return True

    monkeypatch.setattr(scheduler, "publish_pin", fake_publish)
    now = datetime.now(timezone.utc)
    with db() as s:
        for pid, t in zip(ids[:2], [now - timedelta(hours=1), now - timedelta(minutes=5)]):
            p = s.get(Pin, pid)
            p.status = "scheduled"
            p.scheduled_time = t
            p.image_path = str(img)
        # third stays future
        p3 = s.get(Pin, ids[2]); p3.status = "scheduled"
        p3.scheduled_time = now + timedelta(days=1)
        s.commit()
        published, failed = scheduler.run_due(s, now=now)
        assert published == 2 and failed == 0
        assert len(fetches) == 1                    # fetched once for whole run


def test_run_due_backoff_and_cap(db, monkeypatch):
    from pinterest_automation.config.settings import Settings
    from pinterest_automation.database.models import Pin
    from pinterest_automation.services.scheduler import MAX_RETRIES, run_due
    ids = _ready_pins(db, 2)
    monkeypatch.setattr("pinterest_automation.processors.uploader.publish_pin",
                        lambda *a, **k: False)
    # patch the name imported INTO scheduler module:
    import pinterest_automation.services.scheduler as sched_mod
    monkeypatch.setattr(sched_mod, "publish_pin", lambda *a, **k: False)
    monkeypatch.setattr(sched_mod, "get_boards", lambda token=None: [])
    cfg = Settings(_env_file=None, post_hours=[0], posts_per_day=5)

    with db() as s:
        low = s.get(Pin, ids[0])           # retry_count 0 -> backoff
        low.status = "scheduled"
        low.scheduled_time = datetime(2026, 1, 10, 7, 0)
        high = s.get(Pin, ids[1])          # retry_count already at cap -> terminal failed
        high.status = "scheduled"
        high.retry_count = MAX_RETRIES
        high.scheduled_time = datetime(2026, 1, 10, 7, 0)
        s.commit()

        published, failed = run_due(s, now=datetime(2026, 1, 10, 8, 0,
                                                    tzinfo=timezone.utc))
        assert published == 0 and failed == 2

        s.refresh(low); s.refresh(high)
        assert low.status == "scheduled"
        assert low.scheduled_time > datetime(2026, 1, 10, 7, 0, tzinfo=timezone.utc)
        assert high.status == "failed"


def test_run_due_boards_failure_backs_off_without_retry_count(db, monkeypatch):
    """Infra failure (get_boards) must not burn pin retry budget."""
    import pinterest_automation.services.scheduler as sched_mod
    from pinterest_automation.database.models import Pin

    def boom(token=None):
        raise RuntimeError("api down")

    monkeypatch.setattr(sched_mod, "get_boards", boom)
    ids = _ready_pins(db, 2)
    now = datetime.now(timezone.utc)
    t0 = now - timedelta(minutes=1)
    with db() as s:
        for pid in ids:
            p = s.get(Pin, pid)
            p.status = "scheduled"
            p.retry_count = 0
            p.scheduled_time = t0
        s.commit()

        published, failed = sched_mod.run_due(s, now=now)
        assert published == 0 and failed == 2
        for pid in ids:
            p = s.get(Pin, pid)
            assert p.status == "scheduled"                    # not terminal
            assert p.retry_count == 0                         # budget untouched
            assert now < p.scheduled_time <= now + timedelta(minutes=16)  # ~15min backoff
            assert "boards" in (p.error_message or "")
