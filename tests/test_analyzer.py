import json

import pytest

VALID = {
    "title": "Aesthetic Anime Wallpaper for Phone with Dark Moody Vibes HD",
    "description": "y" * 310,
    "alt_text": "Dark moody anime wallpaper of a lone figure.",
    "primary_keyword": "anime wallpaper",
    "secondary_keywords": [f"kw{i}" for i in range(11)],
    "tags": [f"tag{i}" for i in range(16)],
    "board": "Anime Wallpapers",
    "category": "Anime",
}


@pytest.fixture
def db(tmp_path):
    from pinterest_automation.database.db import make_session_factory
    return make_session_factory(f"sqlite:///{tmp_path}/t.db")


@pytest.fixture
def fake_gen(monkeypatch):
    from pinterest_automation.services import analyzer

    seen = []

    def gen(image_path):
        seen.append(image_path)
        if "bad" in str(image_path):
            raise analyzer.MetadataValidationError("boom")
        from types import SimpleNamespace
        return SimpleNamespace(**VALID)

    monkeypatch.setattr(analyzer, "generate_metadata", gen)
    return seen


def test_analyzes_batch_and_marks_ready(db, fake_gen, tmp_path):
    from pinterest_automation.database.models import Pin
    from pinterest_automation.services.analyzer import analyze_pending
    imgs = []
    for i in range(3):
        p = tmp_path / f"img{i}.png"; p.write_bytes(b"x"); imgs.append(p)
    with db() as s:
        for i, p in enumerate(imgs):
            s.add(Pin(image_path=str(p), image_hash=f"h{i}"))
        s.commit()
        n = analyze_pending(s)
        assert n == 3
        rows = s.query(Pin).all()
        assert all(r.status == "ready" for r in rows)
        r0 = rows[0]
        assert r0.title == VALID["title"]
        assert json.loads(r0.secondary_keywords)[0] == "kw0"
        assert json.loads(r0.tags) == VALID["tags"]
        assert r0.ai_called_at is not None


def test_failure_keeps_pending_with_error(db, fake_gen, tmp_path):
    from pinterest_automation.database.models import Pin
    from pinterest_automation.services.analyzer import analyze_pending
    bad = tmp_path / "bad.png"; bad.write_bytes(b"x")
    good = tmp_path / "good.png"; good.write_bytes(b"x")
    with db() as s:
        s.add(Pin(image_path=str(bad), image_hash="hb"))
        s.add(Pin(image_path=str(good), image_hash="hg"))
        s.commit()
        n = analyze_pending(s)
        assert n == 1
        statuses = {r.image_hash: r for r in s.query(Pin)}
        assert statuses["hb"].status == "pending"
        assert statuses["hb"].retry_count == 1
        assert statuses["hb"].error_message
        assert statuses["hg"].status == "ready"


def test_missing_file_fails_row(db, fake_gen, tmp_path):
    from pinterest_automation.database.models import Pin
    from pinterest_automation.services.analyzer import analyze_pending
    with db() as s:
        s.add(Pin(image_path="/does/not/exist.png", image_hash="hx"))
        s.commit()
        analyze_pending(s)
        row = s.query(Pin).one()
        assert row.status == "failed"
        assert "missing" in row.error_message.lower()


def test_limit_respected(db, fake_gen, tmp_path):
    from pinterest_automation.database.models import Pin
    from pinterest_automation.services.analyzer import analyze_pending
    with db() as s:
        for i in range(5):
            p = tmp_path / f"l{i}.png"; p.write_bytes(b"x")
            s.add(Pin(image_path=str(p), image_hash=f"hl{i}"))
        s.commit()
        assert analyze_pending(s, limit=2) == 2


def test_batch_size_drives_loop(db, fake_gen, tmp_path, monkeypatch):
    from pinterest_automation.database.models import Pin
    from pinterest_automation.services.analyzer import analyze_pending
    from pinterest_automation.config.settings import settings
    monkeypatch.setattr(settings, "batch_size", 2)
    with db() as s:
        for i in range(5):
            p = tmp_path / f"b{i}.png"; p.write_bytes(b"x")
            s.add(Pin(image_path=str(p), image_hash=f"hb{i}"))
        s.commit()
        # batch_size=2: first query takes 2, loop continues until fewer than take returned
        n = analyze_pending(s)
        assert n == 5


def test_terminates_when_all_fail(db, tmp_path, monkeypatch):
    from pinterest_automation.config.settings import settings
    from pinterest_automation.database.models import Pin
    from pinterest_automation.services import analyzer
    from pinterest_automation.services.analyzer import analyze_pending

    def always_boom(p):
        raise RuntimeError("api down")

    monkeypatch.setattr(settings, "batch_size", 2)
    monkeypatch.setattr(analyzer, "generate_metadata", always_boom)
    with db() as s:
        for i in range(4):
            p = tmp_path / f"f{i}.png"; p.write_bytes(b"x")
            s.add(Pin(image_path=str(p), image_hash=f"hf{i}"))
        s.commit()
        assert analyze_pending(s) == 0                     # returns, does not spin forever
        rows = s.query(Pin).all()
        assert all(r.status == "pending" and r.retry_count == 1 for r in rows)
