import io
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image


@pytest.fixture
def client(tmp_path, monkeypatch):
    from pinterest_automation.api import rest
    from pinterest_automation.config import settings as cfgmod
    from pinterest_automation.database import db as dbmod

    f = dbmod.make_session_factory(f"sqlite:///{tmp_path}/t.db")
    monkeypatch.setattr(dbmod, "get_session_factory", lambda: f)
    monkeypatch.setattr(cfgmod.settings, "images_dir", tmp_path / "storage")

    app = FastAPI()
    app.include_router(rest.router)
    return f, TestClient(app)


def _png_bytes(w=10, h=10, color=(200, 30, 30)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (w, h), color).save(buf, format="PNG")
    return buf.getvalue()


def _upload(client, files: list[tuple[str, bytes]]):
    payload = [("files", (name, content, "image/png")) for name, content in files]
    return client.post("/api/uploads", files=payload)


def test_upload_adds_pending_pins_with_metadata(client):
    f, c = client
    a_bytes, b_bytes = _png_bytes(64, 32), _png_bytes(20, 20, (0, 255, 0))
    r = _upload(c, [("a.png", a_bytes), ("b.png", b_bytes)])
    assert r.status_code == 201
    body = r.json()
    assert len(body["added"]) == 2 and body["duplicates"] == []
    pin = body["added"][0]
    assert pin["status"] == "pending"
    assert pin["filename"] == "a.png"
    assert pin["width"] == 64 and pin["height"] == 32
    assert pin["file_size"] == len(a_bytes)
    assert pin["image_url"] == f"/media/{pin['id']}"
    from pinterest_automation.database.models import Pin
    with f() as s:
        row = s.query(Pin).filter(Pin.id == pin["id"]).one()
        assert Path(row.image_path).is_file()
        assert str(Path(row.image_path)).startswith(str(Path(row.image_path).parent))


def test_upload_duplicate_content_goes_to_duplicates(client):
    f, c = client
    data = _png_bytes(50, 50)
    _upload(c, [("first.png", data)])
    r = _upload(c, [("second.png", data)])
    body = r.json()
    assert body["added"] == [] and body["duplicates"] == ["second.png"]


def test_upload_rejects_bad_extension(client):
    f, c = client
    r = _upload(c, [("evil.exe", b"MZ")])
    body = r.json()
    assert body["added"] == []
    assert body["rejected"] == [{"filename": "evil.exe", "reason": "unsupported type"}]


def test_upload_rejects_oversize(client, monkeypatch):
    f, c = client
    from pinterest_automation.api import rest
    monkeypatch.setattr(rest, "MAX_UPLOAD_BYTES", 10)
    r = _upload(c, [("big.png", _png_bytes() + b"padpadpad")])
    body = r.json()
    assert body["added"] == []
    assert body["rejected"] == [{"filename": "big.png", "reason": "too large"}]


def test_upload_emits_events(client):
    f, c = client
    from pinterest_automation.services import events
    q = events.subscribe()
    try:
        _upload(c, [("evt.png", _png_bytes(8, 8))])
        seen = [q.get_nowait() for _ in range(q.qsize())]
    finally:
        events.unsubscribe(q)
    types = [e["type"] for e in seen]
    assert "image.uploaded" in types
    evt = next(e for e in seen if e["type"] == "image.uploaded")
    assert evt["payload"]["filename"] == "evt.png"
    assert "path" in evt["payload"]


def test_traversal_filename_is_sanitized(client, tmp_path):
    f, c = client
    r = _upload(c, [("../escaped.png", _png_bytes(12, 12))])
    assert r.status_code == 201
    body = r.json()
    assert len(body["added"]) == 1
    assert body["added"][0]["filename"] == "escaped.png"
    # nothing written outside images_dir (tmp_path/storage)
    assert not (tmp_path / "escaped.png").exists()
    from pinterest_automation.database.models import Pin
    with f() as s:
        row = s.query(Pin).filter(Pin.id == body["added"][0]["id"]).one()
        assert str(Path(row.image_path).resolve()).startswith(
            str((tmp_path / "storage").resolve()))


def test_upload_same_name_different_content_both_saved(client):
    f, c = client
    r1 = _upload(c, [("a.png", _png_bytes(30, 30))])
    r2 = _upload(c, [("a.png", _png_bytes(40, 40, (9, 9, 9)))])
    assert len(r1.json()["added"]) == 1 and len(r2.json()["added"]) == 1
    from pinterest_automation.database.models import Pin
    with f() as s:
        paths = [p.image_path for p in s.query(Pin).order_by(Pin.id).all()]
    assert Path(paths[0]).name == "a.png"
    assert Path(paths[1]).name == "a (1).png"


def test_upload_failed_duplicate_is_retried(client):
    f, c = client
    data = _png_bytes(50, 50)
    _upload(c, [("first.png", data)])
    from pinterest_automation.database.models import Pin
    with f() as s:
        s.query(Pin).update({Pin.status: "failed"}, synchronize_session=False)
        s.commit()
    r = _upload(c, [("again.png", data)])
    body = r.json()
    assert body["added"] == []
    assert body["duplicates"] == []
    assert len(body["retried"]) == 1
    assert body["retried"][0]["status"] == "pending"


def test_upload_published_duplicate_is_skipped(client):
    f, c = client
    data = _png_bytes(50, 50)
    _upload(c, [("first.png", data)])
    from pinterest_automation.database.models import Pin
    with f() as s:
        s.query(Pin).update({Pin.status: "published"}, synchronize_session=False)
        s.commit()
    r = _upload(c, [("again.png", data)])
    body = r.json()
    assert body["added"] == []
    assert body["retried"] == []
    assert body["duplicates"] == ["again.png"]
