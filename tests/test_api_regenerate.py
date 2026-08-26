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


def _fake_metadata():
    from pinterest_automation.services.seo_generator import PinMetadata

    return PinMetadata(
        title="A" * 60,
        description="D" * 300,
        alt_text="alt text here please",
        primary_keyword="kw",
        secondary_keywords=[f"k{i}" for i in range(10)],
        tags=[f"t{i}" for i in range(15)],
        board="Anime Wallpapers",
        category="Anime",
    )


def test_regenerate_sets_ready_and_title(env, monkeypatch, tmp_path):
    from pinterest_automation.services import analyzer

    img = tmp_path / "real.png"
    img.write_bytes(b"data")
    f, c = env
    monkeypatch.setattr(analyzer, "generate_metadata", lambda p: _fake_metadata())
    pid = _add_pin(f, image_path=str(img), image_hash="h1", status="ready")

    r = c.post(f"/api/pins/{pid}/regenerate")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ready"
    assert body["title"] == "A" * 60
    assert body["board_name"] == "Anime Wallpapers"


def test_regenerate_missing_image_409(env):
    f, c = env
    pid = _add_pin(f, image_path="/does/not/exist.png", image_hash="h1")

    r = c.post(f"/api/pins/{pid}/regenerate")
    assert r.status_code == 409


def test_regenerate_unknown_pin_404(env, monkeypatch):
    from pinterest_automation.services import analyzer

    f, c = env
    monkeypatch.setattr(analyzer, "generate_metadata", lambda p: _fake_metadata())

    r = c.post("/api/pins/999999/regenerate")
    assert r.status_code == 404


def test_regenerate_emits_metadata_generated(env, monkeypatch, tmp_path):
    from pinterest_automation.services import analyzer, events

    img = tmp_path / "real.png"
    img.write_bytes(b"data")
    f, c = env
    monkeypatch.setattr(analyzer, "generate_metadata", lambda p: _fake_metadata())
    pid = _add_pin(f, image_path=str(img), image_hash="h1")

    q = events.subscribe()
    try:
        r = c.post(f"/api/pins/{pid}/regenerate")
        assert r.status_code == 200
        seen = []
        while not q.empty():
            seen.append(q.get_nowait())
    finally:
        events.unsubscribe(q)
    assert any(e["type"] == "metadata.generated" for e in seen)
