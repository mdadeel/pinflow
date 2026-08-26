import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

# `image_hash` is a 256-bit SHA256 content hash (64 hex chars), not a perceptual
# hash. We drive the endpoint with controlled hex strings so Hamming distances
# are deterministic. (Exact byte-identical hashes are prevented by the DB unique
# constraint, so a "duplicate" here is a 1-bit-near-identical hash.)
H_BASE = "00" * 32          # 64-char (256-bit) zero hash, mirrors SHA256 width
H_NEAR = "00" * 31 + "01"   # differs from H_BASE by exactly 1 bit
H_FAR = "ff" * 32           # differs from H_BASE by 256 bits


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


def test_near_duplicate_returned_with_high_score(env):
    f, c = env
    target = _add_pin(f, image_hash=H_BASE, title="Target")
    near = _add_pin(f, image_hash=H_NEAR, title="Near Dup", status="ready")
    body = c.get(f"/api/pins/{target}/duplicates").json()
    assert [d["id"] for d in body] == [near]
    assert body[0]["score"] == round(1 - 1 / 256, 4)
    assert body[0]["status"] == "ready"


def test_far_hash_excluded(env):
    f, c = env
    target = _add_pin(f, image_hash=H_BASE)
    _add_pin(f, image_hash=H_FAR, title="Far")
    assert c.get(f"/api/pins/{target}/duplicates").json() == []


def test_null_hash_returns_empty(env):
    f, c = env
    pid = _add_pin(f, image_hash="")  # no hash
    assert c.get(f"/api/pins/{pid}/duplicates").json() == []


def test_unknown_pin_404(env):
    f, c = env
    assert c.get("/api/pins/999999/duplicates").status_code == 404
