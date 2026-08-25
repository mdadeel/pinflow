from datetime import timedelta
from types import SimpleNamespace

import pytest


@pytest.fixture
def db(tmp_path, monkeypatch):
    from pinterest_automation.database import db as dbmod
    f = dbmod.make_session_factory(f"sqlite:///{tmp_path}/t.db")
    monkeypatch.setattr(dbmod, "get_session_factory", lambda: f)
    return f


def _fake_meta():
    return SimpleNamespace(title="T" * 65, description="D" * 310, alt_text="An image",
                           primary_keyword="k", secondary_keywords=["a"] * 12,
                           tags=["t"] * 16, board="Anime Board", category="Anime")


def test_run_once_end_to_end(db, monkeypatch, tmp_path):
    from pinterest_automation.database.db import utcnow
    from pinterest_automation.database.models import Pin
    from pinterest_automation.services import analyzer
    from pinterest_automation.services import scheduler as sched
    from pinterest_automation import main

    folder = tmp_path / "watch"
    folder.mkdir()
    (folder / "a.png").write_bytes(b"data")
    monkeypatch.setattr(main.settings, "watch_dir", folder)
    monkeypatch.setattr(analyzer, "generate_metadata", lambda p: _fake_meta())

    # run_due resolves publish_pin/get_boards in the scheduler module namespace,
    # so the fakes must go there (patching main.* only covers cmd_publish_now).
    def fake_pub(db_, pin, token=None, boards=None):
        pin.status = "published"
        db_.commit()          # real publish_pin commits; run_due does not re-commit successes
        return True

    monkeypatch.setattr(sched, "publish_pin", fake_pub)
    monkeypatch.setattr(sched, "get_boards", lambda token=None: [])
    monkeypatch.setattr(main, "publish_pin", fake_pub)

    # freshly assigned slots are strictly future (never due), so seed one
    # already-due pin to exercise the publish phase of run-once.
    img = tmp_path / "due.png"
    img.write_bytes(b"x")
    with db() as s:
        s.add(Pin(image_path=str(img), image_hash="duehash", status="scheduled",
                  title="Due", description="D", board_name="Anime Board",
                  scheduled_time=utcnow() - timedelta(minutes=1)))
        s.commit()

    rc = main.run(["run-once"])
    assert rc == 0
    with db() as s:
        due = s.query(Pin).filter(Pin.image_hash == "duehash").one()
        fresh = s.query(Pin).filter(Pin.image_hash != "duehash").one()
        assert due.status == "published"
        assert fresh.scheduled_time is not None


def test_scan_creates_missing_watch_dir(db, monkeypatch, tmp_path):
    from pinterest_automation import main
    folder = tmp_path / "watch"          # does NOT exist yet
    monkeypatch.setattr(main.settings, "watch_dir", folder)
    main.run(["scan"])
    assert folder.exists()               # created instead of crashing


def test_analyze_limit_passthrough(db, monkeypatch):
    from pinterest_automation import main
    seen = {}

    def fake_analyze(session, limit=None):
        seen["limit"] = limit
        return 0

    monkeypatch.setattr(main, "analyze_pending", fake_analyze)
    main.run(["analyze", "--limit", "7"])
    assert seen["limit"] == 7
    main.run(["analyze"])
    assert seen["limit"] is None


def test_schedule_limit_passthrough(db, monkeypatch):
    from pinterest_automation import main
    seen = {}

    monkeypatch.setattr(main, "analyze_pending", lambda s, limit=None: 0)
    monkeypatch.setattr(main, "assign_schedule_times",
                        lambda s, ids: seen.setdefault("ids", ids) or 0)
    main.run(["schedule", "--limit", "3"])   # must not crash; limit applied via query
    main.run(["schedule"])
    assert seen["ids"] == []                 # empty db -> empty id list passed through


def test_publish_now_exit_codes(db, tmp_path, monkeypatch):
    from pinterest_automation.database.models import Pin
    from pinterest_automation import main

    img = tmp_path / "i.png"
    img.write_bytes(b"x")
    with db() as s:
        p = Pin(image_path=str(img), image_hash="h", status="ready",
                title="T", description="D", board_name="Anime Board")
        s.add(p)
        s.commit()
        pid = p.id

    monkeypatch.setattr(main, "publish_pin",
                        lambda db_, pin, token=None, boards=None:
                        setattr(pin, "status", "published") or True)
    assert main.run(["publish-now", "--id", str(pid)]) == 0
    assert main.run(["publish-now", "--id", "999999"]) == 2

    monkeypatch.setattr(main, "publish_pin", lambda db_, pin, token=None, boards=None: False)
    with db() as s:
        s.add(Pin(image_path=str(img), image_hash="h2", status="ready",
                  title="T", description="D", board_name="X"))
        s.commit()
        pid2 = s.query(Pin).order_by(Pin.id.desc()).first().id
    assert main.run(["publish-now", "--id", str(pid2)]) == 1


def test_publish_lock_excludes_concurrent_runs(db, monkeypatch, tmp_path):
    """Holding the lock in-process must make run-once fail fast."""
    from pinterest_automation import main

    folder = tmp_path / "w"
    folder.mkdir()
    monkeypatch.setattr(main.settings, "watch_dir", folder)
    monkeypatch.setattr(main.settings, "log_dir", tmp_path / "logs")

    with main._publish_lock():
        rc = main.run(["run-once"])
        assert rc == 1                       # lock busy -> nonzero, no hang


def test_run_argparse_bad_command_exits(monkeypatch):
    from pinterest_automation import main
    with pytest.raises(SystemExit):
        main.run(["nope"])
