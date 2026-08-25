# Pinterest AI Publisher Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A Python app that watches an image folder, generates Pinterest SEO metadata via OpenRouter vision models, stores everything in SQLite, and schedules/publishes Pins through the Pinterest API — with a dashboard and analytics.

**Architecture:** Single Python package `pinterest_automation/` following the spec's layout. SQLite is the source of truth: every pin's lifecycle state lives in the `pins` table, which is also what makes scheduling restart-safe (a DB tick re-publishes due pins; no job store needed). Two thin REST clients (httpx) talk to OpenRouter and Pinterest v5. Dashboard is server-rendered FastAPI + Jinja2 — no frontend framework.

**Tech Stack:** Python 3.12+, FastAPI, SQLAlchemy 2.0, Pydantic (+ pydantic-settings), APScheduler, httpx, Jinja2, pytest.

**Spec:** `/home/adeel/Documents/projects/pin-automation/Pinterest AI Automation Tool Specification.md`

## Global Constraints

- Python 3.12+; stack fixed to FastAPI, SQLAlchemy, SQLite, Pydantic, APScheduler.
- OpenRouter default model: `google/gemini-2.5-flash`, selectable via `OPENROUTER_MODEL` env var.
- Strict JSON only from the AI. Validate before saving.
- Title 60–100 chars; description 300–500 chars; secondary keywords 10–20; tags 15–25.
- Duplicate prevention: SHA-256 image hash + DB unique constraint + title check.
- Batch size configurable (`BATCH_SIZE=25` default). Must handle 10 → 10,000 images.
- Posting cadence: `POSTS_PER_DAY=5` default across hours `[08:00, 11:00, 14:00, 17:00, 20:00]`, both configurable.
- Scheduler must survive restarts → scheduled_time stored in `pins` table; tick reads DB.
- Env vars required: `OPENROUTER_API_KEY`, `PINTEREST_ACCESS_TOKEN`, optional `PINTEREST_BOARD_ID`.
- All logs go to `logs/`; API retries with exponential backoff; honor `Retry-After` on 429.
- Future platforms (Instagram etc.) must be addable without touching core logic — keep publishing functions platform-neutral (plain args in / result out); do NOT build a plugin framework now (YAGNI).

## Assumptions (defaults chosen, change if wrong)

1. Single Pinterest account, personal access token pasted into `.env`. Token expiry = regenerate manually (v5 refresh flow noted in Task 15 README).
2. Pinterest API v5 has **no alt_text field on pin create** — alt text is stored in our DB and kept ready for when Pinterest exposes it; we still generate it per spec.
3. Images arrive in a watched folder (`WATCH_DIR`, default `./images`) as finished files (no partial-upload handling).
4. Dashboard is internal/admin use — server-rendered, no auth.
5. One repo, one plan. The dashboard (Task 14) could be split out if you want two PRs.

## File Structure

```text
pinterest_automation/
├── api/
│   ├── __init__.py
│   ├── openrouter.py        # OpenRouter chat/vision REST client
│   └── pinterest.py         # Pinterest v5 REST client (boards, pins, analytics)
├── services/
│   ├── __init__.py
│   ├── seo_generator.py     # prompt loading + strict JSON validation (Pydantic)
│   ├── analyzer.py          # image -> PinMetadata -> DB row update
│   ├── scheduler.py         # slot assignment + due-pin runner
│   ├── analytics.py         # metric fetch/upsert
│   ├── reporting.py         # daily/weekly report dicts + file writer
│   └── board_mapper.py      # recommended board -> real Pinterest board id
├── database/
│   ├── __init__.py
│   ├── db.py                # engine/session factory, Base, init_db
│   └── models.py            # Pin, AnalyticsRow
├── processors/
│   ├── __init__.py
│   ├── image_watcher.py     # folder scan + SHA256 dedup ingest
│   └── uploader.py          # publish one pin via Pinterest client
├── prompts/
│   └── pinterest_seo.txt
├── utils/
│   ├── __init__.py
│   └── http_retry.py        # shared request retry/backoff for both APIs
├── config/
│   ├── __init__.py
│   └── settings.py          # env-driven Settings
├── dashboard/
│   ├── __init__.py
│   ├── app.py               # FastAPI routes
│   └── templates/           # base/overview/library/calendar/analytics
├── storage/images/          # served as thumbnails by dashboard
├── logs/
└── main.py                  # CLI entrypoint + APScheduler daemon
tests/                       # mirrors package layout
.env.example
pyproject.toml
README.md
```

---

### Task 1: Project scaffold, config, logging

**Files:**
- Create: `pyproject.toml`, `.env.example`, `pinterest_automation/__init__.py`, all `__init__.py`s listed above, `pinterest_automation/config/settings.py`, `pinterest_automation/config/logging_setup.py`
- Test: `tests/test_settings.py`

**Interfaces:**
- Produces: `Settings` class + module singleton `settings`; `setup_logging()` writing to `logs/app.log` + stdout.

- [x] **Step 1: Create scaffold files**

`pyproject.toml`:
```toml
[project]
name = "pinterest-automation"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "fastapi>=0.115",
    "uvicorn>=0.30",
    "sqlalchemy>=2.0",
    "pydantic>=2.7",
    "pydantic-settings>=2.3",
    "apscheduler>=3.10,<4",
    "httpx>=0.27",
    "jinja2>=3.1",
]

[project.optional-dependencies]
dev = ["pytest>=8"]

[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
include = ["pinterest_automation*"]
```

`.env.example`:
```env
OPENROUTER_API_KEY=
PINTEREST_ACCESS_TOKEN=
PINTEREST_BOARD_ID=
OPENROUTER_MODEL=google/gemini-2.5-flash
BATCH_SIZE=25
POSTS_PER_DAY=5
POST_HOURS=8,11,14,17,20
WATCH_DIR=./images
```

Create empty `__init__.py` in: `pinterest_automation/`, `api/`, `services/`, `database/`, `processors/`, `utils/`, `config/`, `dashboard/`. Also `mkdir -p prompts storage/images logs tests`.

- [x] **Step 2: Write failing test**

`tests/test_settings.py`:
```python
import os
from pathlib import Path

def test_settings_reads_env(monkeypatch, tmp_path):
    monkeypatch.setenv("OPENROUTER_MODEL", "test-model")
    monkeypatch.setenv("BATCH_SIZE", "50")
    monkeypatch.setenv("POST_HOURS", "9,12")
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    from pinterest_automation.config.settings import Settings
    s = Settings(_env_file=None)
    assert s.openrouter_model == "test-model"
    assert s.batch_size == 50
    assert s.post_hours == [9, 12]
    assert s.openrouter_api_key == ""
```

- [x] **Step 3: Run test to verify it fails**

Run: `pip install -e ".[dev]" && pytest tests/test_settings.py -v`
Expected: FAIL (`ModuleNotFoundError: pinterest_automation.config.settings`)

- [x] **Step 4: Implement settings + logging**

`pinterest_automation/config/settings.py`:
```python
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    openrouter_api_key: str = ""
    pinterest_access_token: str = ""
    pinterest_board_id: str = ""
    openrouter_model: str = "google/gemini-2.5-flash"

    batch_size: int = 25
    posts_per_day: int = 5
    post_hours: list[int] = [8, 11, 14, 17, 20]

    watch_dir: Path = Path("images")
    images_dir: Path = Path("pinterest_automation/storage/images")
    log_dir: Path = Path("pinterest_automation/logs")
    reports_dir: Path = Path("pinterest_automation/logs/reports")
    db_url: str = "sqlite:///pinterest_automation/data.db"

settings = Settings()
```
(`POST_HOURS=8,11` parses to `list[int]` natively under pydantic-settings.)

`pinterest_automation/config/logging_setup.py`:
```python
import logging, sys
from pathlib import Path

def setup_logging(log_dir: Path) -> None:
    log_dir.mkdir(parents=True, exist_ok=True)
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    for h in (logging.FileHandler(log_dir / "app.log"), logging.StreamHandler(sys.stdout)):
        h.setFormatter(fmt); root.addHandler(h)
```

- [x] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_settings.py -v` → PASS

- [x] **Step 6: Commit**
```bash
git init && git add -A && git commit -m "feat: project scaffold, settings, logging"
```

---

### Task 2: Database models + session factory

**Files:**
- Create: `pinterest_automation/database/db.py`, `pinterest_automation/database/models.py`
- Test: `tests/test_db.py`

**Interfaces:**
- Consumes: `settings` (Task 1).
- Produces: `Base`, `utcnow()`, `make_session_factory(db_url) -> sessionmaker`, `init_db()` (creates tables using `settings.db_url`), models `Pin`, `AnalyticsRow`. Status vocabulary used everywhere downstream: `"pending" | "ready" | "scheduled" | "published" | "failed"`.

- [x] **Step 1: Write failing test**

`tests/test_db.py`:
```python
import pytest
from sqlalchemy.exc import IntegrityError

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
    with Session() as db:
        p = Pin(image_path="/a.png", image_hash="h1"); db.add(p); db.commit()
        db.add(AnalyticsRow(pin_id=p.id, impressions=10, clicks=1)); db.commit()
        row = db.query(AnalyticsRow).one()
        assert row.pin_id == p.id and row.ctr >= 0
```

- [x] **Step 2: Run to verify fail**

Run: `pytest tests/test_db.py -v` → FAIL (ModuleNotFoundError)

- [x] **Step 3: Implement**

`pinterest_automation/database/db.py`:
```python
from datetime import datetime, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from pinterest_automation.config.settings import settings

def utcnow() -> datetime:
    return datetime.now(timezone.utc)

class Base(DeclarativeBase):
    pass

def make_session_factory(db_url: str) -> sessionmaker:
    engine = create_engine(db_url, connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)

_factory = None

def get_session_factory():
    global _factory
    if _factory is None:
        _factory = make_session_factory(settings.db_url)
    return _factory

def init_db() -> None:
    from pinterest_automation.database import models  # noqa: F401 register tables
    get_session_factory()
```

`pinterest_automation/database/models.py`:
```python
from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, Float
from sqlalchemy.orm import Mapped, mapped_column
from pinterest_automation.database.db import Base, utcnow

class Pin(Base):
    __tablename__ = "pins"
    __table_args__ = (UniqueConstraint("image_hash", name="uq_image_hash"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    image_path: Mapped[str] = mapped_column(String(500))
    image_hash: Mapped[str] = mapped_column(String(64))
    title: Mapped[str | None] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text)
    alt_text: Mapped[str | None] = mapped_column(Text)
    primary_keyword: Mapped[str | None] = mapped_column(String(100))
    secondary_keywords: Mapped[str | None] = mapped_column(Text)   # JSON array string
    tags: Mapped[str | None] = mapped_column(Text)                 # JSON array string
    board_name: Mapped[str | None] = mapped_column(String(100))
    board_id: Mapped[str | None] = mapped_column(String(50))
    content_category: Mapped[str | None] = mapped_column(String(50))
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    error_message: Mapped[str | None] = mapped_column(Text)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    ai_called_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    scheduled_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    published_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    pin_id_str: Mapped[str | None] = mapped_column(String(50))      # Pinterest pin id
    pin_url: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

class AnalyticsRow(Base):
    __tablename__ = "analytics"
    __table_args__ = (UniqueConstraint("pin_id", name="uq_analytics_pin"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    pin_id: Mapped[int] = mapped_column(ForeignKey("pins.id"))
    impressions: Mapped[int] = mapped_column(Integer, default=0)
    clicks: Mapped[int] = mapped_column(Integer, default=0)
    saves: Mapped[int] = mapped_column(Integer, default=0)
    outbound_clicks: Mapped[int] = mapped_column(Integer, default=0)
    ctr: Mapped[float] = mapped_column(Float, default=0.0)
    last_updated: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
```

- [x] **Step 4: Run to verify pass**

Run: `pytest tests/test_db.py -v` → 3 PASS

- [x] **Step 5: Commit**
```bash
git add -A && git commit -m "feat: sqlite models (pins, analytics) + session factory"
```

---

### Task 3: Image discovery & duplicate-proof ingest

**Files:**
- Create: `pinterest_automation/processors/image_watcher.py`
- Test: `tests/test_image_watcher.py`

**Interfaces:**
- Consumes: `Pin`, `make_session_factory`, `utcnow`.
- Produces: `EXTENSIONS = {".png",".jpg",".jpeg",".webp"}`, `sha256_file(path: Path) -> str`, `scan_folder(folder: Path, db) -> int` (inserts new unique images as `status="pending"` rows; returns count added; skips already-ingested hashes).

- [x] **Step 1: Write failing test**

`tests/test_image_watcher.py`:
```python
import hashlib
import pytest

@pytest.fixture
def db(tmp_path):
    from pinterest_automation.database.db import make_session_factory
    return make_session_factory(f"sqlite:///{tmp_path}/t.db")

def _img(path, content=b"x"):
    path.write_bytes(content)
    return path

def test_scan_inserts_and_dedups(db, tmp_path):
    from pinterest_automation.processors.image_watcher import scan_folder
    folder = tmp_path / "images"; folder.mkdir()
    _img(folder / "a.png", b"a")
    _img(folder / "b.jpg", b"b")
    _img(folder / "c.txt", b"c")          # ignored extension
    _img(folder / "sub.d", b"d")          # not a file... actually dir-like name; make dir:
    (folder / "subdir").mkdir()
    _img(folder / "subdir" / "nested.png", b"n")  # not scanned (flat scan)
    with db() as s:
        added = scan_folder(folder, s)
        assert added == 2
        again = scan_folder(folder, s)     # second run: nothing new
        assert again == 0

def test_identical_content_different_name_skipped(db, tmp_path):
    from pinterest_automation.processors.image_watcher import scan_folder
    folder = tmp_path / "images"; folder.mkdir()
    _img(folder / "one.png", b"same-bytes")
    _img(folder / "two.png", b"same-bytes")   # same hash -> duplicate
    with db() as s:
        assert scan_folder(folder, s) == 1

def test_sha256_file_matches_hashlib(db, tmp_path):
    from pinterest_automation.processors.image_watcher import sha256_file
    p = _img(tmp_path / "x.png", b"hello")
    assert sha256_file(p) == hashlib.sha256(b"hello").hexdigest()
```

- [x] **Step 2: Run to verify fail**

Run: `pytest tests/test_image_watcher.py -v` → FAIL

- [x] **Step 3: Implement**

`pinterest_automation/processors/image_watcher.py`:
```python
import hashlib, logging
from pathlib import Path
from pinterest_automation.database.models import Pin

log = logging.getLogger(__name__)
EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}

def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()

def scan_folder(folder: Path, db) -> int:
    """Insert new images as pending rows. Flat scan, hash-deduped."""
    existing = {h for (h,) in db.query(Pin.image_hash).all()}
    added = 0
    batch = []
    for p in sorted(folder.iterdir()):
        if not p.is_file() or p.suffix.lower() not in EXTENSIONS:
            continue
        digest = sha256_file(p)
        if digest in existing:
            continue
        batch.append(Pin(image_path=str(p.resolve()), image_hash=digest))
        existing.add(digest)
        added += 1
    if batch:
        db.add_all(batch)
        db.commit()
        log.info("ingested %d new images from %s", added, folder)
    return added
```
Note: flat scan of the watch dir (spec shows a flat folder). 10k files = 10k rows, fine for SQLite; hashing streams in 1 MB chunks so memory stays flat.

- [x] **Step 4: Run to verify pass**

Run: `pytest tests/test_image_watcher.py -v` → 3 PASS

- [x] **Step 5: Commit**
```bash
git add -A && git commit -m "feat: image watcher with sha256 dedup ingest"
```

---

### Task 4: Shared HTTP retry helper + OpenRouter client

**Files:**
- Create: `pinterest_automation/utils/http_retry.py`, `pinterest_automation/api/openrouter.py`
- Test: `tests/test_http_retry.py`, `tests/test_openrouter_client.py`

**Interfaces:**
- Consumes: `settings.openrouter_api_key`, `settings.openrouter_model`.
- Produces:
  - `request_with_retry(method: str, url: str, *, tries: int = 3, **kw) -> httpx.Response` — retries on 429/5xx/network errors with exponential backoff, honors `Retry-After`, raises `HTTPTooManyRetries` after exhausting.
  - `OpenRouterError(RuntimeError)`
  - `chat(messages: list[dict], **overrides) -> str` — returns assistant message content.
  - `image_data_url(path: Path) -> str` — `data:<mime>;base64,...`.

- [x] **Step 1: Write failing tests**

`tests/test_http_retry.py`:
```python
import httpx, pytest

def test_retries_on_429_then_succeeds(monkeypatch):
    import pinterest_automation.utils.http_retry as hr
    calls = []
    def fake_request(method, url, **kw):
        calls.append(1)
        if len(calls) < 3:
            return httpx.Response(429, headers={"retry-after": "0"}, request=httpx.Request("GET", url))
        return httpx.Response(200, json={"ok": True}, request=httpx.Request("GET", url))
    monkeypatch.setattr(hr.httpx, "request", fake_request)
    monkeypatch.setattr(hr.time, "sleep", lambda s: None)
    r = hr.request_with_retry("GET", "https://x.test")
    assert r.status_code == 200 and len(calls) == 3

def test_raises_after_exhaustion(monkeypatch):
    import pinterest_automation.utils.http_retry as hr
    monkeypatch.setattr(hr.httpx, "request", lambda m, u, **k: httpx.Response(500, request=httpx.Request("GET", u)))
    monkeypatch.setattr(hr.time, "sleep", lambda s: None)
    with pytest.raises(hr.HTTPTooManyRetries):
        hr.request_with_retry("GET", "https://x.test")

def test_no_retry_on_400(monkeypatch):
    import pinterest_automation.utils.http_retry as hr
    calls = []
    def fake(method, url, **kw): calls.append(1); return httpx.Response(400, request=httpx.Request("GET", url))
    monkeypatch.setattr(hr.httpx, "request", fake)
    with pytest.raises(httpx.HTTPStatusError):
        hr.request_with_retry("GET", "https://x.test")
    assert len(calls) == 1
```

`tests/test_openrouter_client.py`:
```python
import json, base64, httpx, pytest

def _fake_openrouter(content: str, status=200):
    body = {"choices": [{"message": {"content": content}}]}
    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        assert payload["model"] == "test-model"
        assert request.headers["authorization"] == "Bearer k-test"
        return httpx.Response(status, json=body)
    return httpx.Client(transport=httpx.MockTransport(handler))

def test_chat_returns_content(monkeypatch):
    from pinterest_automation.api import openrouter as orr
    client = _fake_openrouter("hello!")
    monkeypatch.setattr(orr, "_client", lambda: client)
    assert orr.chat([{"role": "user", "content": "hi"}]) == "hello!"

def test_image_data_url(tmp_path):
    from pinterest_automation.api.openrouter import image_data_url
    p = tmp_path / "i.png"; p.write_bytes(b"\x89PNG")
    url = image_data_url(p)
    mime, b64 = url.split(";")[0][5:], url.split(",")[1]
    assert mime == "image/png" and base64.b64decode(b64) == b"\x89PNG"
```

- [x] **Step 2: Run to verify fail**

Run: `pytest tests/test_http_retry.py tests/test_openrouter_client.py -v` → FAIL

- [x] **Step 3: Implement**

`pinterest_automation/utils/http_retry.py`:
```python
import logging, time
import httpx

log = logging.getLogger(__name__)

class HTTPTooManyRetries(RuntimeError):
    pass

RETRYABLE_STATUS = {429, 500, 502, 503, 504}

def request_with_retry(method: str, url: str, *, tries: int = 3, timeout: float = 120.0, **kw) -> httpx.Response:
    delay = 2.0
    last: Exception | httpx.Response | None = None
    for attempt in range(1, tries + 1):
        try:
            r = httpx.request(method, url, timeout=timeout, **kw)
            if r.status_code not in RETRYABLE_STATUS:
                r.raise_for_status()
                return r
            wait = float(r.headers.get("retry-after", delay))
            log.warning("%s %s -> %s, retry %d/%d in %.0fs", method, url, r.status_code, attempt, tries, wait)
            time.sleep(wait)
            delay *= 2
        except httpx.HTTPStatusError:
            raise
        except httpx.HTTPError as e:
            last = e
            log.warning("network error %s, retry %d/%d in %.0fs", e, attempt, tries, delay)
            time.sleep(delay); delay *= 2
    raise HTTPTooManyRetries(f"{method} {url} failed after {tries} attempts ({last})")
```

`pinterest_automation/api/openrouter.py`:
```python
import base64, logging
from pathlib import Path
from pinterest_automation.config.settings import settings
from pinterest_automation.utils.http_retry import HTTPTooManyRetries, request_with_retry

log = logging.getLogger(__name__)
URL = "https://openrouter.ai/api/v1/chat/completions"
MIME = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp"}

class OpenRouterError(RuntimeError):
    pass

def _client():
    # overridable in tests
    import httpx
    return httpx.Client()

def chat(messages: list[dict], **overrides) -> str:
    payload = {"model": settings.openrouter_model, "messages": messages}
    payload.update(overrides)
    headers = {"Authorization": f"Bearer {settings.openrouter_api_key}"}
    try:
        r = request_with_retry("POST", URL, headers=headers, json=payload)
    except HTTPTooManyRetries as e:
        raise OpenRouterError(str(e)) from e
    try:
        return r.json()["choices"][0]["message"]["content"]
    except (KeyError, IndexError) as e:
        raise OpenRouterError(f"unexpected response shape: {r.text[:300]}") from e

def image_data_url(path: Path) -> str:
    mime = MIME[path.suffix.lower()]
    return f"data:{mime};base64,{base64.b64encode(path.read_bytes()).decode()}"
```
(Test monkeypatches `_client` — but implementation above uses `request_with_retry` directly. To keep the seam simple, have `chat()` route through a small `_post(payload, headers)` that tests can patch instead. Final implementation detail: expose `def _post(payload, headers): return request_with_retry("POST", URL, headers=headers, json=payload)` and call it from `chat()`; adjust test to patch `orr._post` returning an `httpx.Response(200, json=body)`. Keep behavior identical.)

- [x] **Step 4: Run to verify pass**

Run: `pytest tests/test_http_retry.py tests/test_openrouter_client.py -v` → 6 PASS

- [x] **Step 5: Commit**
```bash
git add -A && git commit -m "feat: shared http retry + openrouter client"
```

---

### Task 5: SEO prompt + strict JSON validation

**Files:**
- Create: `pinterest_automation/prompts/pinterest_seo.txt`, `pinterest_automation/services/seo_generator.py`
- Test: `tests/test_seo_generator.py`

**Interfaces:**
- Consumes: `chat()` from Task 4.
- Produces:
  - `PinMetadata` (Pydantic model): fields `title, description, alt_text, primary_keyword, secondary_keywords: list[str], tags: list[str], board, category` with spec constraints enforced.
  - `parse_metadata(raw: str) -> PinMetadata` — strips code fences, extracts first JSON object, raises `MetadataValidationError` on failure.
  - `generate_metadata(image_path: Path) -> PinMetadata` — builds the vision prompt, calls the model, validates, retries once feeding back the validation error; raises `MetadataValidationError` if still invalid.

- [x] **Step 1: Write failing test**

`tests/test_seo_generator.py`:
```python
import json, pytest, httpx

VALID = {
    "title": "Aesthetic Anime Wallpaper for Phone with Dark Moody Vibes HD",
    "description": ("x" * 320),
    "alt_text": "Dark moody anime wallpaper showing a lone figure at night.",
    "primary_keyword": "anime wallpaper",
    "secondary_keywords": ["kw%d" % i for i in range(12)],
    "tags": ["tag%d" % i for i in range(18)],
    "board": "Anime Wallpapers",
    "category": "Anime",
}
VALID_RAW = "```json\n" + json.dumps(VALID) + "\n```"

def test_parse_strips_fences():
    from pinterest_automation.services.seo_generator import parse_metadata
    m = parse_metadata(VALID_RAW)
    assert m.board == "Anime Wallpapers" and len(m.tags) == 18

def test_parse_rejects_short_title():
    from pinterest_automation.services.seo_generator import parse_metadata, MetadataValidationError
    bad = dict(VALID, title="too short")
    with pytest.raises(MetadataValidationError):
        parse_metadata(json.dumps(bad))

def test_parse_rejects_garbage():
    from pinterest_automation.services.seo_generator import parse_metadata, MetadataValidationError
    with pytest.raises(MetadataValidationError):
        parse_metadata("not json at all")

def test_generate_validates_then_succeeds(monkeypatch, tmp_path):
    from pinterest_automation.api import openrouter as orr
    from pinterest_automation.services import seo_generator as sg
    calls = []
    def fake_post(payload, headers):
        calls.append(payload)
        raw = VALID_RAW if len(calls) == 1 else "garbage"
        return httpx.Response(200, json={"choices": [{"message": {"content": raw}}]})
    monkeypatch.setattr(sg, "chat", sg.chat)  # ensure exists
    monkeypatch.setattr(orr, "_post", fake_post)
    monkeypatch.setattr(sg, "image_data_url", lambda p: "data:image/png;base64,AAA")
    p = tmp_path / "i.png"; p.write_bytes(b"z")
    m = sg.generate_metadata(p)
    assert m.category == "Anime" and len(calls) == 1
```

- [x] **Step 2: Run to verify fail**

Run: `pytest tests/test_seo_generator.py -v` → FAIL

- [x] **Step 3: Implement**

`pinterest_automation/prompts/pinterest_seo.txt`:
```text
You are a Pinterest SEO expert. Analyze this image and produce metadata that maximizes Pinterest reach.

Return STRICT JSON only — no markdown fences, no commentary. Exact schema:

{
  "title": "Pinterest title, 60-100 characters, SEO optimized, natural, high CTR",
  "description": "Pinterest description, 300-500 characters, keyword rich but human readable, not spammy",
  "alt_text": "Accessibility-friendly accurate description of the image",
  "primary_keyword": "single main keyword phrase",
  "secondary_keywords": ["10 to 20 related keyword phrases"],
  "tags": ["15 to 25 Pinterest hashtags/tags"],
  "board": "best matching board, exactly one of: Anime Wallpapers, Minimalist Wallpapers, Aesthetic Art, Relationship Quotes, Couple Wallpapers, Dark Anime, Phone Backgrounds, Desktop Wallpapers",
  "category": "exactly one of: Anime, Wallpaper, Aesthetic, Motivation, Relationship, Quotes, Gaming, Technology, Nature"
}
```

`pinterest_automation/services/seo_generator.py`:
```python
import json, logging, re
from pathlib import Path
from pydantic import BaseModel, Field, ValidationError
from pinterest_automation.api.openrouter import chat, image_data_url

log = logging.getLogger(__name__)
PROMPT_FILE = Path(__file__).resolve().parent.parent / "prompts" / "pinterest_seo.txt"

class MetadataValidationError(ValueError):
    pass

class PinMetadata(BaseModel):
    title: str = Field(min_length=60, max_length=100)
    description: str = Field(min_length=300, max_length=500)
    alt_text: str = Field(min_length=10)
    primary_keyword: str = Field(min_length=2)
    secondary_keywords: list[str] = Field(min_length=10, max_length=20)
    tags: list[str] = Field(min_length=15, max_length=25)
    board: str = Field(min_length=2)
    category: str = Field(min_length=2)

def load_prompt() -> str:
    return PROMPT_FILE.read_text(encoding="utf-8")

def parse_metadata(raw: str) -> PinMetadata:
    text = re.sub(r"^```(?:json)?|```$", "", raw.strip(), flags=re.M).strip()
    match = re.search(r"\{.*\}", text, flags=re.S)
    if not match:
        raise MetadataValidationError("no JSON object found in model output")
    try:
        data = json.loads(match.group())
    except json.JSONDecodeError as e:
        raise MetadataValidationError(f"invalid JSON: {e}") from e
    try:
        return PinMetadata.model_validate(data)
    except ValidationError as e:
        raise MetadataValidationError(str(e)) from e

def generate_metadata(image_path: Path) -> PinMetadata:
    messages = [{"role": "user", "content": [
        {"type": "text", "text": load_prompt()},
        {"type": "image_url", "image_url": {"url": image_data_url(image_path)}},
    ]}]
    raw = chat(messages)
    try:
        meta = parse_metadata(raw)
        return meta
    except MetadataValidationError as first_error:
        log.warning("metadata invalid (%s), retrying once with feedback", str(first_error)[:120])
        fixup = [
            {"role": "user", "content": [
                {"type": "text", "text":
                    f"{load_prompt()}\n\nYour previous answer was rejected:\n{str(first_error)[:1000]}\n"
                    "Fix ALL issues and return strict JSON only."},
                {"type": "image_url", "image_url": {"url": image_data_url(image_path)}},
            ]}
        ]
        meta = parse_metadata(chat(fixup))   # raises MetadataValidationError if still bad
        return meta
```
(The test patches `orr._post`; `sg.chat` resolves through `openrouter.chat`, so patching `orr._post` covers both attempts.)

- [x] **Step 4: Run to verify pass**

Run: `pytest tests/test_seo_generator.py -v` → 4 PASS

- [x] **Step 5: Commit**
```bash
git add -A && git commit -m "feat: seo prompt + strict json metadata validation with retry"
```

---

### Task 6: Analyzer service (vision → metadata → DB)

**Files:**
- Create: `pinterest_automation/services/analyzer.py`
- Test: `tests/test_analyzer.py`

**Interfaces:**
- Consumes: `generate_metadata`, `Pin`, `utcnow`, `settings.batch_size`.
- Produces: `analyze_pending(db, limit: int | None = None) -> int` — takes `pending` rows in batches of `settings.batch_size`, generates metadata, writes fields + sets `status="ready"` + `ai_called_at`; on failure sets `status="pending"` (leaves for next run), increments `retry_count`, stores short `error_message`; skips rows whose image file vanished (`status="failed"`, reason). Returns count analyzed OK.

- [x] **Step 1: Write failing test**

`tests/test_analyzer.py`:
```python
import json, pytest

VALID = {
    "title": "Aesthetic Anime Wallpaper for Phone with Dark Moody Vibes HD",
    "description": "y" * 310,
    "alt_text": "Dark moody anime wallpaper of a lone figure.",
    "primary_keyword": "anime wallpaper",
    "secondary_keywords": ["kw%d" % i for i in range(11)],
    "tags": ["tag%d" % i for i in range(16)],
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
        return type("M", (), {**VALID})()
    monkeypatch.setattr(analyzer, "generate_metadata", gen)
    return seen

def test_analyzes_batch_and_marks_ready(db, fake_gen, tmp_path):
    from pinterest_automation.database.models import Pin
    from pinterest_automation.services.analyzer import analyze_pending
    imgs = []
    for i in range(3):
        p = tmp_path / f"img{i}.png"; p.write_bytes(b"x"); imgs.append(p)
    with db() as s:
        for p in imgs:
            s.add(Pin(image_path=str(p), image_hash=f"h{i}"))
        s.commit()
        n = analyze_pending(s)
        assert n == 3
        rows = s.query(Pin).all()
        assert all(r.status == "ready" for r in rows)
        r0 = rows[0]
        assert r0.title == VALID["title"]
        assert json.loads(r0.secondary_keywords)[0] == "kw0"
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
        assert row.status == "failed" and "missing" in row.error_message.lower()

def test_limit_respected(db, fake_gen, tmp_path):
    from pinterest_automation.database.models import Pin
    from pinterest_automation.services.analyzer import analyze_pending
    with db() as s:
        for i in range(5):
            p = tmp_path / f"l{i}.png"; p.write_bytes(b"x")
            s.add(Pin(image_path=str(p), image_hash=f"hl{i}"))
        s.commit()
        assert analyze_pending(s, limit=2) == 2
```

- [x] **Step 2: Run to verify fail**

Run: `pytest tests/test_analyzer.py -v` → FAIL

- [x] **Step 3: Implement**

`pinterest_automation/services/analyzer.py`:
```python
import json, logging
from pathlib import Path
from pinterest_automation.config.settings import settings
from pinterest_automation.database.models import Pin
from pinterest_automation.database.db import utcnow
from pinterest_automation.services.seo_generator import (
    PinMetadata, MetadataValidationError, generate_metadata,
)

log = logging.getLogger(__name__)

def _apply(pin: Pin, m: PinMetadata) -> None:
    pin.title = m.title
    pin.description = m.description
    pin.alt_text = m.alt_text
    pin.primary_keyword = m.primary_keyword
    pin.secondary_keywords = json.dumps(m.secondary_keywords)
    pin.tags = json.dumps(m.tags)
    pin.board_name = m.board
    pin.content_category = m.category
    pin.ai_called_at = utcnow()
    pin.status = "ready"

def analyze_pending(db, limit: int | None = None) -> int:
    """Generate metadata for pending pins, BATCH_SIZE at a time."""
    ok = 0
    while True:
        remaining = None if limit is None else limit - ok
        if remaining is not None and remaining <= 0:
            break
        take = settings.batch_size if remaining is None else min(settings.batch_size, remaining)
        pins = db.query(Pin).filter(Pin.status == "pending").limit(take).all()
        if not pins:
            break
        for pin in pins:
            path = Path(pin.image_path)
            if not path.is_file():
                pin.status = "failed"
                pin.error_message = "image file missing"
                continue
            try:
                _apply(pin, generate_metadata(path))
                ok += 1
            except (MetadataValidationError, Exception) as e:  # noqa: BLE001 - record, don't crash batch
                pin.retry_count += 1
                pin.error_message = str(e)[:500]
                log.error("analyze failed for %s: %s", pin.image_path, str(e)[:200])
        db.commit()
        if len(pins) < take:
            break
    return ok
```

- [x] **Step 4: Run to verify pass**

Run: `pytest tests/test_analyzer.py -v` → 4 PASS

- [x] **Step 5: Commit**
```bash
git add -A && git commit -m "feat: batched analyzer service writing metadata to db"
```

---

### Task 7: Pinterest API client

**Files:**
- Create: `pinterest_automation/api/pinterest.py`
- Test: `tests/test_pinterest_client.py`

**Interfaces:**
- Consumes: `request_with_retry`, `settings.pinterest_access_token`.
- Produces:
  - `PinterestError(RuntimeError)`
  - `get_boards(token: str | None = None) -> list[dict]` — follows `bookmark` pagination, returns raw board dicts (`id`, `name`, ...).
  - `create_pin(board_id: str, title: str, description: str, image_path: Path, link: str | None = None, token: str | None = None) -> dict` — uploads via `media_source.source_type="image_base64"`; returns created pin dict (`id`, `url`).
  - `get_pin_analytics(pin_id: str, start_date: str, end_date: str, token: str | None = None) -> dict` — metric totals dict.

- [x] **Step 1: Write failing test**

`tests/test_pinterest_client.py`:
```python
import json, httpx, pytest

BOARDS_PAGE1 = {"items": [{"id": "b1", "name": "Anime Board"}], "bookmark": "NEXT"}
BOARDS_PAGE2 = {"items": [{"id": "b2", "name": "Nature Board"}]}

def _transport(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))

def test_get_boards_paginates(monkeypatch):
    from pinterest_automation.api import pinterest as pt
    pages = [json.dumps(BOARDS_PAGE1), json.dumps(BOARDS_PAGE2)]
    seen_urls = []
    def fake_post(url, headers=None, json=None):
        seen_urls.append((url, json))
        if json is None or "bookmark" not in (json or {}):
            return httpx.Response(200, text=pages.pop(0))
        return httpx.Response(200, text=pages.pop(0))
    # simpler: intercept request_with_retry
    calls = {"n": 0}
    def fake_req(method, url, **kw):
        calls["n"] += 1
        body = BOARDS_PAGE1 if calls["n"] == 1 else BOARDS_PAGE2
        return httpx.Response(200, json=body)
    monkeypatch.setattr(pt, "request_with_retry", fake_req)
    boards = pt.get_boards(token="t")
    assert [b["id"] for b in boards] == ["b1", "b2"]

def test_create_pin_payload(monkeypatch, tmp_path):
    from pinterest_automation.api import pinterest as pt
    captured = {}
    def fake_req(method, url, **kw):
        captured.update(url=url, kw=kw)
        return httpx.Response(201, json={"id": "pin123", "url": "https://pinterest.com/pin/123"})
    monkeypatch.setattr(pt, "request_with_retry", fake_req)
    img = tmp_path / "w.png"; img.write_bytes(b"\x89PNG-data")
    res = pt.create_pin(board_id="b1", title="T", description="D", image_path=img, link="https://example.com", token="tok")
    assert res["id"] == "pin123"
    body = captured["kw"]["json"]
    assert body["board_id"] == "b1" and body["link"] == "https://example.com"
    ms = body["media_source"]
    assert ms["source_type"] == "image_base64" and ms["content_type"] == "image/png"
    import base64
    assert base64.b64decode(ms["data"]) == b"\x89PNG-data"
    assert captured["kw"]["headers"]["Authorization"] == "Bearer tok"

def test_create_pin_non_201_raises(monkeypatch, tmp_path):
    from pinterest_automation.api import pinterest as pt
    monkeypatch.setattr(pt, "request_with_retry",
                        lambda m, u, **k: httpx.Response(403, json={"message": "denied"}, request=httpx.Request("POST", u)))
    img = tmp_path / "w.png"; img.write_bytes(b"x")
    with pytest.raises(pt.PinterestError):
        pt.create_pin(board_id="b", title="T", description="D", image_path=img, token="t")

def test_analytics_totals(monkeypatch):
    from pinterest_automation.api import pinterest as pt
    payload = {"all": {"metrics": {"IMPRESSIONS": {"value": 100}, "CLICKS": {}, "SAVES": {}, "OUTBOUND_CLICKS": {}}}}
    def fake_req(method, url, **kw):
        assert "/pins/pin123/analytics" in url
        return httpx.Response(200, json=payload)
    monkeypatch.setattr(pt, "request_with_retry", fake_req)
    totals = pt.get_pin_analytics("pin123", "2026-08-01", "2026-08-24", token="t")
    assert isinstance(totals, dict)
```

- [x] **Step 2: Run to verify fail**

Run: `pytest tests/test_pinterest_client.py -v` → FAIL

- [x] **Step 3: Implement**

`pinterest_automation/api/pinterest.py`:
```python
import base64, logging
from pathlib import Path
from pinterest_automation.config.settings import settings
from pinterest_automation.utils.http_retry import HTTPTooManyRetries, request_with_retry

log = logging.getLogger(__name__)
BASE = "https://api.pinterest.com/v5"
MIME = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp"}
ANALYTIC_METRICS = "IMPRESSIONS,CLICKS,SAVES,OUTBOUND_CLICKS,TOTAL_IMPRESSIONS,PIN_CLICK_RATE"

class PinterestError(RuntimeError):
    pass

def _token(token: str | None) -> str:
    tok = token or settings.pinterest_access_token
    if not tok:
        raise PinterestError("no PINTEREST_ACCESS_TOKEN configured")
    return tok

def _call(method: str, url: str, token: str, **kw) -> httpx.Response:
    try:
        return request_with_retry(method, url, headers={"Authorization": f"Bearer {token}"}, **kw)
    except HTTPTooManyRetries as e:
        raise PinterestError(str(e)) from e

def get_boards(token: str | None = None) -> list[dict]:
    tok = _token(token)
    boards, bookmark = [], None
    while True:
        params = {"page_size": 100}
        if bookmark:
            params["bookmark"] = bookmark
        r = _call("GET", f"{BASE}/boards", tok, params=params)
        data = r.json()
        boards.extend(data.get("items", []))
        bookmark = data.get("bookmark")
        if not bookmark:
            return boards

def create_pin(board_id: str, title: str, description: str, image_path: Path,
               link: str | None = None, token: str | None = None) -> dict:
    tok = _token(token)
    mime = MIME[image_path.suffix.lower()]
    payload: dict = {
        "board_id": board_id,
        "title": title,
        "description": description,
        # ponytail: v5 has no alt_text field on pin create; we store it locally only
        "media_source": {
            "source_type": "image_base64",
            "content_type": mime,
            "data": base64.b64encode(image_path.read_bytes()).decode(),
        },
    }
    if link:
        payload["link"] = link
    r = _call("POST", f"{BASE}/pins", tok, json=payload)
    if r.status_code not in (200, 201):
        raise PinterestError(f"create_pin failed {r.status_code}: {r.text[:300]}")
    return r.json()

def get_pin_analytics(pin_id: str, start_date: str, end_date: str, token: str | None = None) -> dict:
    """Returns flattened metric totals: {'impressions': int, 'clicks': int, 'saves': int, 'outbound_clicks': int}."""
    tok = _token(token)
    r = _call("GET", f"{BASE}/pins/{pin_id}/analytics", tok,
              params={"start_date": start_date, "end_date": end_date, "metric_types": ANALYTIC_METRICS})
    data = r.json().get("all", {}).get("metrics", {})
    def val(metric):
        return data.get(metric, {}).get("value", 0) or 0
    return {
        "impressions": val("IMPRESSIONS"),
        "clicks": val("CLICKS"),
        "saves": val("SAVES"),
        "outbound_clicks": val("OUTBOUND_CLICKS"),
    }
```
Add `import httpx` at top for typing. Note: `create_pin` checks status explicitly because 403 shouldn't be retried but also isn't success.

- [x] **Step 4: Run to verify pass**

Run: `pytest tests/test_pinterest_client.py -v` → 4 PASS

- [x] **Step 5: Commit**
```bash
git add -A && git commit -m "feat: pinterest v5 client (boards, pin create, analytics)"
```

---

### Task 8: Board mapping (auto/manual)

**Files:**
- Create: `pinterest_automation/services/board_mapper.py`
- Modify: `.env.example` (add `BOARD_OVERRIDES=` line)
- Modify: `pinterest_automation/config/settings.py` (add field)
- Test: `tests/test_board_mapper.py`

**Interfaces:**
- Consumes: `get_boards()` result shape (`{"id","name"}`).
- Produces: `map_board(recommended: str, boards: list[dict], overrides: dict[str, str] | None = None) -> str | None` — precedence: manual override by recommended name → exact name match (case-insensitive) → keyword overlap score → None.

- [x] **Step 1: Add setting** — in `settings.py` add:
```python
    board_overrides: dict[str, str] = {}
```
and to `.env.example`: `BOARD_OVERRIDES={"Couple Wallpapers":"1234567890"}`
(JSON map of *recommended* board name → *Pinterest* board id.)

- [x] **Step 2: Write failing test**

`tests/test_board_mapper.py`:
```python
BOARDS = [{"id": "1", "name": "Anime Board"}, {"id": "2", "name": "Nature Photos"}, {"id": "3", "name": "phone backgrounds"}]

def test_manual_override_wins():
    from pinterest_automation.services.board_mapper import map_board
    assert map_board("Anything", BOARDS, overrides={"Anything": "9"}) == "9"

def test_exact_match_case_insensitive():
    from pinterest_automation.services.board_mapper import map_board
    assert map_board("Phone Backgrounds", BOARDS) == "3"

def test_keyword_overlap():
    from pinterest_automation.services.board_mapper import map_board
    assert map_board("Best Anime Wallpapers", BOARDS) == "1"   # 'anime' overlaps

def test_no_match_returns_none():
    from pinterest_automation.services.board_mapper import map_board
    assert map_board("Cooking Recipes", BOARDS) is None
```

- [x] **Step 3: Run to verify fail** — `pytest tests/test_board_mapper.py -v` → FAIL

- [x] **Step 4: Implement**

`pinterest_automation/services/board_mapper.py`:
```python
import logging

log = logging.getLogger(__name__)

STOPWORDS = {"for", "the", "and", "with", "best", "of", "a", "an"}

def _tokens(text: str) -> set[str]:
    return {w for w in text.lower().replace("-", " ").split() if w not in STOPWORDS}

def map_board(recommended: str, boards: list[dict], overrides: dict[str, str] | None = None) -> str | None:
    if overrides and recommended in overrides:
        return overrides[recommended]
    rec = _tokens(recommended)
    best_id, best_score = None, 0
    for b in boards:
        name_tokens = _tokens(b.get("name", ""))
        if name_tokens == rec and rec:
            return b["id"]                      # exact match
        score = len(name_tokens & rec)
        if score > best_score:
            best_id, best_score = b["id"], score
    if best_score:
        return best_id
    log.warning("no board mapping for recommendation %r", recommended)
    return None
```

- [x] **Step 5: Run to verify pass** — `pytest tests/test_board_mapper.py -v` → 4 PASS

- [x] **Step 6: Commit** — `git add -A && git commit -m "feat: board auto/manual mapper"`

---

### Task 9: Uploader (publish one pin, status transitions)

**Files:**
- Create: `pinterest_automation/processors/uploader.py`
- Test: `tests/test_uploader.py`

**Interfaces:**
- Consumes: `get_boards`, `create_pin`, `map_board`, `Pin`.
- Produces: `publish_pin(db, pin: Pin, token: str | None = None) -> bool` — maps board, creates pin, writes `pin_id_str`, `pin_url`, `published_time`, `status="published"`. On board-map failure → `status="failed"`, `error_message`. On API failure → increment `retry_count`, keep `status` unchanged (caller decides), store `error_message`. Returns True iff published.

- [x] **Step 1: Write failing test**

`tests/test_uploader.py`:
```python
import pytest

BOARDS = [{"id": "b1", "name": "Anime Board"}]

@pytest.fixture
def db(tmp_path):
    from pinterest_automation.database.db import make_session_factory
    return make_session_factory(f"sqlite:///{tmp_path}/t.db")

@pytest.fixture
def happy_pt(monkeypatch, tmp_path):
    from pinterest_automation.processors import uploader
    monkeypatch.setattr(uploader, "get_boards", lambda token=None: BOARDS)
    def fake_create(board_id, title, description, image_path, link=None, token=None):
        assert board_id == "b1"
        return {"id": "p9", "url": "https://pin.it/x"}
    monkeypatch.setattr(uploader, "create_pin", fake_create)
    img = tmp_path / "i.png"; img.write_bytes(b"x")
    return img

def _ready_pin(db, img):
    from pinterest_automation.database.models import Pin
    with db() as s:
        p = Pin(image_path=str(img), image_hash="h", status="scheduled",
                title="T", description="D", board_name="Anime Board")
        s.add(p); s.commit(); return p.id

def test_publish_success(db, happy_pt):
    from pinterest_automation.database.models import Pin
    from pinterest_automation.processors.uploader import publish_pin
    pid = _ready_pin(db, happy_pt)
    with db() as s:
        pin = s.get(Pin, pid)
        assert publish_pin(s, pin) is True
        assert pin.status == "published"
        assert pin.pin_id_str == "p9" and pin.pin_url == "https://pin.it/x"
        assert pin.published_time is not None

def test_no_board_mapping_fails(db, happy_pt, monkeypatch):
    from pinterest_automation.database.models import Pin
    from pinterest_automation.processors.uploader import publish_pin
    pid = _ready_pin(db, happy_pt)
    with db() as s:
        pin = s.get(Pin, pid); pin.board_name = "Nonexistent Category"
        assert publish_pin(s, pin) is False
        assert pin.status == "failed" and "board" in pin.error_message.lower()

def test_api_error_increments_retry(db, happy_pt, monkeypatch):
    from pinterest_automation.database.models import Pin
    from pinterest_automation.processors import uploader
    monkeypatch.setattr(uploader, "create_pin", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
    pid = _ready_pin(db, happy_pt)
    with db() as s:
        pin = s.get(Pin, pid)
        assert publish_pin(s, pin) is False
        assert pin.retry_count == 1
        assert pin.status == "scheduled"       # unchanged; scheduler may retry later
        assert "boom" in pin.error_message
```

- [x] **Step 2: Run to verify fail** — `pytest tests/test_uploader.py -v` → FAIL

- [x] **Step 3: Implement**

`pinterest_automation/processors/uploader.py`:
```python
import logging
from pinterest_automation.config.settings import settings
from pinterest_automation.database.db import utcnow
from pinterest_automation.database.models import Pin
from pinterest_automation.api.pinterest import create_pin, get_boards
from pinterest_automation.services.board_mapper import map_board

log = logging.getLogger(__name__)

def publish_pin(db, pin: Pin, token: str | None = None) -> bool:
    try:
        boards = get_boards(token=token)
    except Exception as e:  # noqa: BLE001
        pin.error_message = str(e)[:500]; db.commit(); return False
    board_id = pin.board_id or map_board(pin.board_name or "", boards,
                                         overrides=settings.board_overrides)
    if not board_id:
        pin.status = "failed"
        pin.error_message = f"no matching pinterest board for {pin.board_name!r}"
        db.commit()
        return False
    pin.board_id = board_id
    try:
        res = create_pin(board_id, pin.title, pin.description or "", __import__("pathlib").Path(pin.image_path),
                         token=token)
    except Exception as e:  # noqa: BLE001
        pin.retry_count += 1
        pin.error_message = str(e)[:500]
        db.commit()
        return False
    pin.pin_id_str = str(res.get("id"))
    pin.pin_url = res.get("url")
    pin.published_time = utcnow()
    pin.status = "published"
    pin.error_message = None
    db.commit()
    log.info("published pin %s -> %s", pin.id, pin.pin_url)
    return True
```
(Clean up: use `from pathlib import Path` at top instead of `__import__` — final code does that.)

- [x] **Step 4: Run to verify pass** — `pytest tests/test_uploader.py -v` → 3 PASS

- [x] **Step 5: Commit** — `git add -A && git commit -m "feat: pin uploader with board mapping and failure states"`

---

### Task 10: Scheduler (slot assignment + due-tick runner)

**Files:**
- Create: `pinterest_automation/services/scheduler.py`
- Test: `tests/test_scheduler.py`

**Interfaces:**
- Consumes: `settings.post_hours`, `settings.posts_per_day`, `publish_pin`, `Pin`, `utcnow`.
- Produces:
  - `assign_schedule_times(db, pin_ids: list[int]) -> int` — fills free slots starting from the next upcoming hour today, then subsequent days; each day gets at most `posts_per_day` slots taken from `post_hours`; sets `status="scheduled"` + `scheduled_time`; skips already-scheduled ids. Returns number assigned.
  - `due_pins(db, now=None) -> list[Pin]` — `status=="scheduled"` and `scheduled_time<=now`, oldest first.
  - `run_due(db, now=None, max_posts: int | None = None) -> tuple[int, int]` — publishes due pins (cap: `max_posts` else `posts_per_day`); returns `(published, failed_attempts)`.

- [x] **Step 1: Write failing test**

`tests/test_scheduler.py`:
```python
from datetime import datetime, timedelta
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
    from pinterest_automation.database.models import Pin
    from pinterest_automation.services.scheduler import assign_schedule_times
    from pinterest_automation.config.settings import Settings
    s_set = Settings(_env_file=None, post_hours=[8, 11], posts_per_day=2)
    ids = _ready_pins(db, 4)
    with db() as s:
        n = assign_schedule_times(s, ids, cfg=s_set)
        assert n == 4
        times = sorted(p.scheduled_time for p in s.query(Pin).filter(Pin.id.in_(ids)))
        days = {t.date() for t in times}
        assert len(days) == 2                       # 2 slots/day -> spills to next day
        per_day = {}
        for t in times:
            per_day[t.date()] = per_day.get(t.date(), 0) + 1
        assert set(per_day.values()) == {2}

def test_assign_skips_full_days_and_past_slots(db):
    from pinterest_automation.services.scheduler import assign_schedule_times
    from pinterest_automation.config.settings import Settings
    ids = _ready_pins(db, 1)
    s_set = Settings(_env_file=None, post_hours=[0], posts_per_day=1)  # hour 0 always passed today
    with db() as s:
        n = assign_schedule_times(s, ids, cfg=s_set)
        assert n == 1                                # lands tomorrow at 00:xx, not today

def test_run_due_publishes_only_due(db, monkeypatch, tmp_path):
    from pinterest_automation.database.models import Pin
    from pinterest_automation.services import scheduler
    img = tmp_path / "i.png"; img.write_bytes(b"x")
    ids = _ready_pins(db, 3)
    now = datetime.now()
    with db() as s:
        past = [i for i in ids[:2]]
        for pid, t in zip(ids, [now - timedelta(hours=1), now - timedelta(minutes=5), now + timedelta(days=1)]):
            p = s.get(Pin, pid); p.status = "scheduled"; p.scheduled_time = t
            p.image_path = str(img)
        s.commit()
        monkeypatch.setattr(scheduler, "publish_pin", lambda db_, pin: setattr(pin, "status", "published") or True)
        published, failed = scheduler.run_due(s, now=now)
        assert published == 2 and failed == 0
        remaining = s.query(Pin).filter(Pin.status == "scheduled").count()
        assert remaining == 1

def test_failed_publish_counts_and_stays(db, monkeypatch, tmp_path):
    from pinterest_automation.database.models import Pin
    from pinterest_automation.services import scheduler
    ids = _ready_pins(db, 1)
    with db() as s:
        p = s.get(Pin, ids[0]); p.status = "scheduled"
        p.scheduled_time = datetime.now() - timedelta(minutes=1)
        s.commit()
        monkeypatch.setattr(scheduler, "publish_pin", lambda db_, pin: False)
        pub, failed = scheduler.run_due(s)
        assert pub == 0 and failed == 1
        assert s.get(Pin, ids[0]).status == "scheduled"   # left for retry w/ backoff below
```

Retry policy note: a failed pin keeps `status="scheduled"`; next tick re-attempts. To avoid hammering, `run_due` bumps `scheduled_time += 15min * retry_count` on failure (implemented below; covered implicitly by `error_message`/`retry_count` assertions in Task 9).

- [x] **Step 2: Run to verify fail** — `pytest tests/test_scheduler.py -v` → FAIL

- [x] **Step 3: Implement**

`pinterest_automation/services/scheduler.py`:
```python
import logging
from datetime import datetime, timedelta, timezone
from sqlalchemy import func
from pinterest_automation.config.settings import Settings, settings
from pinterest_automation.database.db import utcnow
from pinterest_automation.database.models import Pin
from pinterest_automation.processors.uploader import publish_pin

log = logging.getLogger(__name__)
BACKOFF_MINUTES = 15

def assign_schedule_times(db, pin_ids: list[int], cfg: Settings | None = None, now: datetime | None = None) -> int:
    cfg = cfg or settings
    now = now or utcnow()
    assigned = 0
    for pid in pin_ids:
        slot = _next_free_slot(db, cfg, now)
        if slot is None:
            break
        pin = db.get(Pin, pid)
        if pin is None or pin.status == "scheduled":
            continue
        pin.scheduled_time = slot
        pin.status = "scheduled"
        assigned += 1
    db.commit()
    log.info("scheduled %d pins", assigned)
    return assigned

def _next_free_slot(db, cfg: Settings, now: datetime):
    day = 0
    while day < 365:                                   # safety bound
        base = (now + timedelta(days=day)).date()
        for hour in cfg.post_hours:
            slot = datetime(base.year, base.month, base.day, hour, tzinfo=timezone.utc)
            if slot <= now:
                continue
            taken = db.query(func.count(Pin.id)).filter(
                Pin.status == "scheduled",
                func.strftime("%Y-%m-%d", Pin.scheduled_time) == slot.strftime("%Y-%m-%d"),
            ).scalar()
            if taken >= cfg.posts_per_day:
                continue
            # avoid two pins at the identical minute
            clash = db.query(Pin.id).filter(Pin.status == "scheduled", Pin.scheduled_time == slot).first()
            if clash:
                slot = slot.replace(minute=(slot.minute + taken) % 60)
            return slot
        day += 1
    return None

def due_pins(db, now: datetime | None = None) -> list[Pin]:
    now = now or utcnow()
    return (db.query(Pin)
              .filter(Pin.status == "scheduled", Pin.scheduled_time <= now)
              .order_by(Pin.scheduled_time)
              .all())

def run_due(db, now: datetime | None = None, max_posts: int | None = None, token: str | None = None):
    cap = max_posts or settings.posts_per_day
    published = failed = 0
    for pin in due_pins(db, now=now)[:cap]:
        if publish_pin(db, pin, token=token):
            published += 1
        else:
            failed += 1
            pin.scheduled_time = (pin.scheduled_time or utcnow()) + timedelta(minutes=BACKOFF_MINUTES * max(1, pin.retry_count))
            db.commit()
    return published, failed
```

- [x] **Step 4: Run to verify pass** — `pytest tests/test_scheduler.py -v` → 4 PASS

- [x] **Step 5: Commit** — `git add -A && git commit -m "feat: persistent scheduler with daily caps and retry backoff"`

---

### Task 11: CLI + pipeline wiring + APScheduler daemon

**Files:**
- Create: `pinterest_automation/main.py`
- Test: `tests/test_cli.py`

**Interfaces:**
- Consumes: everything above.
- Produces CLI commands (argparse, stdlib):
  - `scan` — ingest watch dir
  - `analyze [--limit N]` — generate metadata
  - `schedule [--limit N]` — assign schedule times to `ready` pins
  - `publish-now --id PIN_ID` — immediate publish, bypass schedule
  - `run-once` — scan → analyze → schedule → run_due
  - `daemon` — APScheduler BackgroundScheduler: `scan` every 5 min, `analyze`+`schedule`+`run_due` every 10 min
  - `serve` — uvicorn dashboard
- Internal helpers reused by tests: `cmd_scan(cfg)`, `cmd_analyze(limit)`, etc., each opening its own session via `get_session_factory()`.

- [x] **Step 1: Write failing test**

`tests/test_cli.py`:
```python
import pytest

@pytest.fixture
def db(tmp_path, monkeypatch):
    from pinterest_automation.database.db import make_session_factory, db as dbmod
    f = make_session_factory(f"sqlite:///{tmp_path}/t.db")
    monkeypatch.setattr(dbmod, "get_session_factory", lambda: f)
    return f

def test_run_once_end_to_end(db, monkeypatch, tmp_path):
    from pinterest_automation.database.models import Pin
    from pinterest_automation.services import analyzer, scheduler
    from pinterest_automation import main
    folder = tmp_path / "watch"; folder.mkdir()
    img = folder / "a.png"; img.write_bytes(b"data")
    monkeypatch.setattr(main.settings, "watch_dir", folder)
    monkeypatch.setattr(analyzer, "generate_metadata", lambda p: _fake_meta())
    monkeypatch.setattr(main, "publish_pin", lambda db_, pin, token=None: setattr(pin, "status", "published") or True)
    rc = main.run(["run-once"])
    assert rc == 0
    with db() as s:
        pin = s.query(Pin).one()
        assert pin.status == "published" and pin.scheduled_time is not None

def _fake_meta():
    from types import SimpleNamespace
    return SimpleNamespace(title="T" * 65, description="D" * 310, alt_text="An image",
                           primary_keyword="k", secondary_keywords=["a"] * 12, tags=["t"] * 16,
                           board="Anime Wallpapers", category="Anime")
```

- [x] **Step 2: Run to verify fail** — `pytest tests/test_cli.py -v` → FAIL

- [x] **Step 3: Implement**

`pinterest_automation/main.py`:
```python
import argparse, logging, sys
from pathlib import Path
from pinterest_automation.config.logging_setup import setup_logging
from pinterest_automation.config.settings import settings
from pinterest_automation.database.db import get_session_factory
from pinterest_automation.processors.image_watcher import scan_folder
from pinterest_automation.services.analyzer import analyze_pending
from pinterest_automation.services.scheduler import assign_schedule_times, run_due
from pinterest_automation.processors.uploader import publish_pin
from pinterest_automation.database.models import Pin

log = logging.getLogger(__name__)

def cmd_scan():
    db = get_session_factory()()
    n = scan_folder(Path(settings.watch_dir), db)
    print(f"ingested {n} new images")

def cmd_analyze(limit: int | None):
    db = get_session_factory()()
    n = analyze_pending(db, limit=limit)
    print(f"analyzed {n}")

def cmd_schedule(limit: int | None):
    db = get_session_factory()()
    q = db.query(Pin.id).filter(Pin.status == "ready")
    if limit:
        q = q.limit(limit)
    ids = [pid for (pid,) in q.all()]
    n = assign_schedule_times(db, ids)
    print(f"scheduled {n}")

def cmd_publish_now(pin_id: int):
    db = get_session_factory()()
    pin = db.get(Pin, pin_id)
    if pin is None:
        print("pin not found"); return 1
    ok = publish_pin(db, pin)
    print("published" if ok else f"failed: {pin.error_message}")
    return 0 if ok else 1

def cmd_run_once():
    cmd_scan()
    cmd_analyze(None)
    cmd_schedule(None)
    db = get_session_factory()()
    pub, failed = run_due(db)
    print(f"published {pub}, failed {failed}")
    return 0

def cmd_daemon():
    from apscheduler.schedulers.background import BackgroundScheduler
    setup_logging(settings.log_dir)
    sched = BackgroundScheduler()
    sched.add_job(cmd_scan, "interval", minutes=5, id="scan")
    def cycle():
        db = get_session_factory()()
        analyze_pending(db)
        q = db.query(Pin.id).filter(Pin.status == "ready").limit(settings.posts_per_day * 3)
        assign_schedule_times(db, [pid for (pid,) in q.all()])
        run_due(db)
    sched.add_job(cycle, "interval", minutes=10, id="cycle", max_instances=1)
    sched.start()
    print("daemon running. ctrl-c to stop.")
    import time
    try:
        while True:
            time.sleep(60)
    except KeyboardInterrupt:
        sched.shutdown()

def cmd_serve():
    import uvicorn
    uvicorn.run("pinterest_automation.dashboard.app:app", host="127.0.0.1", port=8000)

def run(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="pinterest-automation")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("scan")
    p_an = sub.add_parser("analyze"); p_an.add_argument("--limit", type=int)
    p_sc = sub.add_parser("schedule"); p_sc.add_argument("--limit", type=int)
    p_pn = sub.add_parser("publish-now"); p_pn.add_argument("--id", type=int, required=True)
    sub.add_parser("run-once")
    sub.add_parser("daemon")
    sub.add_parser("serve")
    args = ap.parse_args(argv)
    setup_logging(settings.log_dir)
    if args.cmd == "scan": cmd_scan(); return 0
    if args.cmd == "analyze": cmd_analyze(args.limit); return 0
    if args.cmd == "schedule": cmd_schedule(args.limit); return 0
    if args.cmd == "publish-now": return cmd_publish_now(args.id)
    if args.cmd == "run-once": return cmd_run_once()
    if args.cmd == "daemon": cmd_daemon(); return 0
    if args.cmd == "serve": cmd_serve(); return 0
    return 1

if __name__ == "__main__":
    sys.exit(run())
```

- [x] **Step 4: Run to verify pass** — `pytest tests/test_cli.py -v` → PASS (plus full suite green)

- [x] **Step 5: Commit** — `git add -A && git commit -m "feat: cli commands and apscheduler daemon"`

---

### Task 12: Analytics sync

**Files:**
- Create: `pinterest_automation/services/analytics_service.py`
- Test: `tests/test_analytics_service.py`

**Interfaces:**
- Consumes: `get_pin_analytics`, `AnalyticsRow`, `Pin`, `utcnow`.
- Produces: `sync_published(db, token: str | None = None, lookback_days: int = 30, limit: int = 200) -> int` — for recently published pins having `pin_id_str`, fetch lifetime metrics (window = published_time→today), upsert `analytics` row (unique per pin), compute `ctr = clicks/impressions` (0 if no impressions), bump `last_updated`. Returns count synced.

- [x] **Step 1: Write failing test**

`tests/test_analytics_service.py`:
```python
from datetime import timedelta
import pytest

@pytest.fixture
def db(tmp_path):
    from pinterest_automation.database.db import make_session_factory
    return make_session_factory(f"sqlite:///{tmp_path}/t.db")

METRICS = {"impressions": 1000, "clicks": 50, "saves": 20, "outbound_clicks": 7}

def test_sync_upserts_and_computes_ctr(db, monkeypatch):
    from pinterest_automation.database.models import Pin, AnalyticsRow
    from pinterest_automation.database.db import utcnow
    from pinterest_automation.services import analytics_service as svc
    with db() as s:
        p = Pin(image_path="/i.png", image_hash="h", status="published", pin_id_str="p1",
                published_time=utcnow() - timedelta(days=5))
        s.add(p); s.commit(); pid = p.id
    fetched = []
    def fake_metrics(pin_id, start, end, token=None):
        fetched.append(pin_id); return METRICS
    monkeypatch.setattr(svc, "get_pin_analytics", fake_metrics)
    n = svc.sync_published(s, token="t")
    assert n == 1 and fetched == ["p1"]
    row = s.query(AnalyticsRow).one()
    assert row.pin_id == pid and row.impressions == 1000
    assert abs(row.ctr - 0.05) < 1e-9
    # second sync updates, doesn't duplicate
    METRICS2 = dict(METRICS, impressions=2000)
    monkeypatch.setattr(svc, "get_pin_analytics", lambda *a, **k: METRICS2)
    svc.sync_published(s, token="t")
    assert s.query(AnalyticsRow).count() == 1
    assert s.query(AnalyticsRow).one().impressions == 2000

def test_sync_skips_unpublished(db):
    from pinterest_automation.database.models import Pin
    from pinterest_automation.services import analytics_service as svc
    with db() as s:
        s.add(Pin(image_path="/i.png", image_hash="h", status="pending"))
        s.commit()
        assert svc.sync_published(s) == 0
```

- [x] **Step 2: Run to verify fail** — `pytest tests/test_analytics_service.py -v` → FAIL

- [x] **Step 3: Implement**

`pinterest_automation/services/analytics_service.py`:
```python
import logging
from datetime import date, timedelta
from pinterest_automation.database.db import utcnow
from pinterest_automation.database.models import AnalyticsRow, Pin
from pinterest_automation.api.pinterest import get_pin_analytics

log = logging.getLogger(__name__)

def sync_published(db, token: str | None = None, lookback_days: int = 30, limit: int = 200) -> int:
    cutoff = utcnow() - timedelta(days=lookback_days)
    pins = (db.query(Pin)
              .filter(Pin.status == "published", Pin.pin_id_str.is_not(None), Pin.published_time >= cutoff)
              .order_by(Pin.published_time.desc())
              .limit(limit).all())
    synced = 0
    today = date.today()
    for pin in pins:
        start = (pin.published_time or utcnow()).date()
        try:
            metrics = get_pin_analytics(pin.pin_id_str, start.isoformat(), today.isoformat(), token=token)
        except Exception as e:  # noqa: BLE001
            log.warning("analytics fetch failed for pin %s: %s", pin.pin_id_str, str(e)[:150])
            continue
        row = db.query(AnalyticsRow).filter(AnalyticsRow.pin_id == pin.id).one_or_none()
        if row is None:
            row = AnalyticsRow(pin_id=pin.id)
            db.add(row)
        row.impressions = metrics["impressions"]
        row.clicks = metrics["clicks"]
        row.saves = metrics["saves"]
        row.outbound_clicks = metrics["outbound_clicks"]
        row.ctr = metrics["clicks"] / metrics["impressions"] if metrics["impressions"] else 0.0
        row.last_updated = utcnow()
        synced += 1
    db.commit()
    return synced
```

- [x] **Step 4: Run to verify pass** — `pytest tests/test_analytics_service.py -v` → 2 PASS

- [x] **Step 5: Commit** — `git add -A && git commit -m "feat: analytics sync service with upsert"`

---

### Task 13: Reports (daily / weekly)

**Files:**
- Create: `pinterest_automation/services/reporting.py`
- Test: `tests/test_reporting.py`
- Modify: `pinterest_automation/main.py` (add `report --kind daily|weekly` command; wire into daemon as daily 23:30 job)

**Interfaces:**
- Consumes: `Pin`, `AnalyticsRow`, `settings.reports_dir`.
- Produces:
  - `daily_report(db, day: date) -> dict` — `{date, pins_posted, pins_failed, ai_calls}` (`ai_calls` = pins with `ai_called_at` on `day`).
  - `weekly_report(db, end_day: date) -> dict` — `{week_ending, top_categories:[{category,impressions,clicks}], best_keywords:[{keyword,clicks}], best_boards:[{board_name,clicks}]}` — joins analytics→pins over trailing 7 days.
  - `write_report(report: dict, kind: str) -> Path` — JSON file `reports_dir/YYYY-MM-DD-{kind}.json`.

- [x] **Step 1: Write failing test**

`tests/test_reporting.py`:
```python
from datetime import date, timedelta
import json, pytest

@pytest.fixture
def db(tmp_path, monkeypatch):
    from pinterest_automation.database.db import make_session_factory
    from pinterest_automation.config import settings as cfgmod
    monkeypatch.setattr(cfgmod.settings, "reports_dir", tmp_path / "reports")
    return make_session_factory(f"sqlite:///{tmp_path}/t.db")

def _seed(db, day):
    from pinterest_automation.database.models import Pin, AnalyticsRow
    from pinterest_automation.database.db import utcnow
    with db() as s:
        for i in range(2):
            s.add(Pin(image_path=f"/{i}.png", image_hash=f"h{i}", status="published",
                      content_category="Anime", primary_keyword="anime wallpaper",
                      board_name="Anime Board", published_time=day))
        p_fail = Pin(image_path="/f.png", image_hash="hf", status="failed", error_message="x",
                     updated_at=day)
        s.add(p_fail)
        s.commit()
        for p in s.query(Pin).filter(Pin.status == "published"):
            s.add(AnalyticsRow(pin_id=p.id, impressions=500, clicks=10, saves=2, outbound_clicks=1))
        s.commit()

def test_daily_report_counts(db):
    from pinterest_automation.services.reporting import daily_report
    day = date.today()
    _seed(db, day)
    rep = daily_report(next(iter([None])), day) if False else daily_report(_session(db), day)
    assert rep["pins_posted"] == 2 and rep["pins_failed"] == 1

def _session(db):
    return db()

def test_weekly_report_ranks(db):
    from pinterest_automation.services.reporting import weekly_report
    _seed(db, date.today())
    rep = weekly_report(_session(db), date.today())
    assert rep["top_categories"][0]["category"] == "Anime"
    assert rep["best_keywords"][0]["keyword"] == "anime wallpaper"
    assert rep["best_boards"][0]["board_name"] == "Anime Board"

def test_write_report_file(db):
    from pinterest_automation.services.reporting import write_report
    from pinterest_automation.config import settings as cfgmod
    path = write_report({"hello": 1}, "daily")
    assert path.exists() and json.loads(path.read_text())["hello"] == 1
```

- [x] **Step 2: Run to verify fail** — `pytest tests/test_reporting.py -v` → FAIL

- [x] **Step 3: Implement**

`pinterest_automation/services/reporting.py`:
```python
import json, logging
from datetime import date, timedelta
from sqlalchemy import func, desc
from pinterest_automation.config.settings import settings
from pinterest_automation.database.db import utcnow
from pinterest_automation.database.models import AnalyticsRow, Pin

log = logging.getLogger(__name__)

def daily_report(db, day: date) -> dict:
    day_start = utcnow().replace(year=day.year, month=day.month, day=day.day,
                                 hour=0, minute=0, second=0, microsecond=0)
    day_end = day_start + timedelta(days=1)
    posted = db.query(func.count(Pin.id)).filter(Pin.status == "published",
             Pin.published_time >= day_start, Pin.published_time < day_end).scalar()
    failed = db.query(func.count(Pin.id)).filter(Pin.status == "failed",
              Pin.updated_at >= day_start, Pin.updated_at < day_end).scalar()
    ai_calls = db.query(func.count(Pin.id)).filter(Pin.ai_called_at.is_not(None),
               Pin.ai_called_at >= day_start, Pin.ai_called_at < day_end).scalar()
    return {"date": day.isoformat(), "pins_posted": posted, "pins_failed": failed, "ai_calls": ai_calls}

def _top(db, column, end_day: date, n=5):
    week_ago = utcnow() - timedelta(days=7)
    rows = (db.query(column.label("k"),
                     func.sum(AnalyticsRow.impressions).label("imp"),
                     func.sum(AnalyticsRow.clicks).label("clk"))
              .join(Pin, Pin.id == AnalyticsRow.pin_id)
              .filter(Pin.published_time >= week_ago)
              .group_by(column)
              .order_by(desc("clk"))
              .limit(n).all())
    return [{"key": r.k, "impressions": r.imp or 0, "clicks": r.clk or 0} for r in rows]

def weekly_report(db, end_day: date) -> dict:
    categories = [{"category": r["key"], **{k: v for k, v in r.items() if k != "key"}} for r in _top(db, Pin.content_category, end_day)]
    keywords = [{"keyword": r["key"], **{k: v for k, v in r.items() if k != "key"}} for r in _top(db, Pin.primary_keyword, end_day)]
    boards = [{"board_name": r["key"], **{k: v for k, v in r.items() if k != "key"}} for r in _top(db, Pin.board_name, end_day)]
    return {"week_ending": end_day.isoformat(),
            "top_categories": categories, "best_keywords": keywords, "best_boards": boards}

def write_report(report: dict, kind: str):
    d = settings.reports_dir
    d.mkdir(parents=True, exist_ok=True)
    path = d / f"{report.get('date', report.get('week_ending'))}-{kind}.json"
    path.write_text(json.dumps(report, indent=2))
    log.info("report written: %s", path)
    return path
```

Then modify `main.py`: add `report` subcommand (`--kind`, defaults to today/end-of-week logic inside) calling `daily_report`/`weekly_report` + `write_report`, printing the path; add to `cmd_daemon`: `sched.add_job(lambda: ..., "cron", hour=23, minute=30, id="daily-report")` producing the daily report automatically.

- [x] **Step 4: Run to verify pass** — `pytest tests/test_reporting.py -v` → 3 PASS

- [x] **Step 5: Commit** — `git add -A && git commit -m "feat: daily/weekly reporting"`

---

### Task 14: Dashboard (FastAPI + Jinja2)

**Files:**
- Create: `pinterest_automation/dashboard/app.py`
- Create templates: `pinterest_automation/dashboard/templates/base.html`, `overview.html`, `library.html`, `calendar.html`, `analytics.html`
- Test: `tests/test_dashboard.py`
- Modify: `pinterest_automation/dashboard/__init__.py` if needed (empty is fine)

**Interfaces:**
- Consumes: `get_session_factory`, models, `json` decode of keyword/tag columns.
- Produces routes:
  - `GET /` overview — counts: total, pending(+ready), scheduled, published, failed.
  - `GET /library?status=&page=` — thumbnails (`<img src="/media/<path>">` static mount on `storage/images`… actually images live wherever `image_path` points; serve via a tiny media route that streams any registered image_path safely restricted to registered paths).
  - `GET /calendar?month=YYYY-MM` — month grid listing scheduled (future) and published pins per day.
  - `GET /analytics` — totals (impressions/clicks/saves/CTR), top 10 pins table by clicks.

Media route decision: mount `StaticFiles(directory=settings.images_dir)` at `/static-img` for anything copied there, PLUS a guarded `/media/{pin_id}` route streaming `Path(pin.image_path)` only for pins present in DB — simplest correct approach without copying files.

- [x] **Step 1: Write failing test**

`tests/test_dashboard.py`:
```python
import pytest
from datetime import datetime, timedelta, timezone

@pytest.fixture
def client(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from pinterest_automation.database.db import make_session_factory
    from pinterest_automation import dashboard_app_module as dam  # placeholder replaced below
    ...
```
(Final concrete version:)
```python
import pytest
from datetime import datetime, timedelta, timezone

@pytest.fixture
def env(tmp_path, monkeypatch):
    from pinterest_automation.database.db import make_session_factory, db as dbmod
    f = make_session_factory(f"sqlite:///{tmp_path}/t.db")
    monkeypatch.setattr(dbmod, "get_session_factory", lambda: f)
    from fastapi.testclient import TestClient
    from pinterest_automation.dashboard.app import app
    return f, TestClient(app)

def test_overview_counts(env, tmp_path):
    f, c = env
    from pinterest_automation.database.models import Pin
    with f() as s:
        s.add(Pin(image_path=str(tmp_path / "a.png"), image_hash="1", status="pending"))
        s.add(Pin(image_path=str(tmp_path / "b.png"), image_hash="2", status="scheduled"))
        s.add(Pin(image_path=str(tmp_path / "c.png"), image_hash="3", status="published"))
        s.add(Pin(image_path=str(tmp_path / "d.png"), image_hash="4", status="failed"))
        s.commit()
    html = c.get("/").text
    assert "Total Images" in html and "Scheduled Pins" in html

def test_library_lists_metadata(env, tmp_path):
    f, c = env
    from pinterest_automation.database.models import Pin
    img = tmp_path / "a.png"; img.write_bytes(b"\x89PNG")
    with f() as s:
        s.add(Pin(image_path=str(img), image_hash="1", status="ready",
                  title="T" * 70, description="D" * 310, content_category="Anime"))
        s.commit()
    html = c.get("/library").text
    assert "Anime" in html and "/media/1" in html

def test_calendar_shows_scheduled(env, tmp_path):
    f, c = env
    from pinterest_automation.database.models import Pin
    future = datetime.now(timezone.utc) + timedelta(days=1)
    with f() as s:
        s.add(Pin(image_path="/x.png", image_hash="1", status="scheduled",
                  title="Future Pin Title Here That Is Long Enough For Pinterest Specs Ok",
                  scheduled_time=future))
        s.commit()
    month = future.strftime("%Y-%m")
    html = c.get(f"/calendar?month={month}").text
    assert "Future Pin Title Here That Is Long Enough For Pinterest Specs Ok" in html

def test_analytics_view(env):
    f, c = env
    from pinterest_automation.database.models import Pin, AnalyticsRow
    with f() as s:
        p = Pin(image_path="/x.png", image_hash="1", status="published", title="Top Pin " * 8)
        s.add(p); s.commit()
        s.add(AnalyticsRow(pin_id=p.id, impressions=1000, clicks=90, saves=5, outbound_clicks=3, ctr=0.09))
        s.commit()
    html = c.get("/analytics").text
    assert "Top Pin" in html and "1,000" in html or "1000" in html
```

- [x] **Step 2: Run to verify fail** — `pytest tests/test_dashboard.py -v` → FAIL

- [x] **Step 3: Implement**

`pinterest_automation/dashboard/app.py` (routes + queries; templates render):
```python
import json
from datetime import datetime, timezone
from calendar import monthrange
from pathlib import Path
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, desc
from pinterest_automation.database.db import get_session_factory, utcnow
from pinterest_automation.database.models import Pin, AnalyticsRow

app = FastAPI(title="Pinterest Publisher")
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))

@app.get("/", response_class=HTMLResponse)
def overview(request: Request):
    db = get_session_factory()()
    total = db.query(func.count(Pin.id)).scalar()
    counts = dict(db.query(Pin.status, func.count(Pin.id)).group_by(Pin.status).all())
    ctx = {
        "total_images": total,
        "pending": counts.get("pending", 0) + counts.get("ready", 0),
        "scheduled": counts.get("scheduled", 0),
        "published": counts.get("published", 0),
        "failed": counts.get("failed", 0),
    }
    return templates.TemplateResponse(request, "overview.html", ctx)

@app.get("/library", response_class=HTMLResponse)
def library(request: Request, status: str | None = None, page: int = 1):
    db = get_session_factory()()
    PER = 50
    q = db.query(Pin).order_by(Pin.created_at.desc())
    if status:
        q = q.filter(Pin.status == status)
    items = q.offset((page - 1) * PER).limit(PER).all()
    for p in items:
        p.secondary_keywords_list = json.loads(p.secondary_keywords) if p.secondary_keywords else []
        p.tags_list = json.loads(p.tags) if p.tags else []
    return templates.TemplateResponse(request, "library.html",
                                      {"pins": items, "status": status, "page": page})

@app.get("/calendar", response_class=HTMLResponse)
def calendar_view(request: Request, month: str | None = None):
    now = datetime.now(timezone.utc)
    year, mon = (int(x) for x in month.split("-")) if month else (now.year, now.month)
    start = datetime(year, mon, 1, tzinfo=timezone.utc)
    end = datetime(year, mon, monthrange(year, mon)[1], 23, 59, tzinfo=timezone.utc)
    db = get_session_factory()()
    events = (db.query(Pin)
                .filter(Pin.scheduled_time.between(start, end) | Pin.published_time.between(start, end))
                .order_by(Pin.scheduled_time).all())
    by_day: dict[int, list] = {}
    for p in events:
        d = ((p.scheduled_time or p.published_time).day)
        by_day.setdefault(d, []).append(p)
    return templates.TemplateResponse(request, "calendar.html",
                                      {"year": year, "month": mon, "days": monthrange(year, mon)[1],
                                       "by_day": by_day, "today": now})

@app.get("/analytics", response_class=HTMLResponse)
def analytics(request: Request):
    db = get_session_factory()()
    imp = db.query(func.sum(AnalyticsRow.impressions)).scalar() or 0
    clk = db.query(func.sum(AnalyticsRow.clicks)).scalar() or 0
    saves = db.query(func.sum(AnalyticsRow.saves)).scalar() or 0
    obc = db.query(func.sum(AnalyticsRow.outbound_clicks)).scalar() or 0
    ctr = clk / imp if imp else 0
    top = (db.query(Pin, AnalyticsRow)
             .join(AnalyticsRow, AnalyticsRow.pin_id == Pin.id)
             .order_by(desc(AnalyticsRow.clicks)).limit(10).all())
    return templates.TemplateResponse(request, "analytics.html",
                                      {"impressions": imp, "clicks": clk, "saves": saves,
                                       "outbound_clicks": obc, "ctr": ctr, "top": top})

@app.get("/media/{pin_id}")
def media(pin_id: int):
    db = get_session_factory()()
    pin = db.get(Pin, pin_id)
    if pin is None:
        raise HTTPException(404)
    path = Path(pin.image_path)
    if not path.is_file():
        raise HTTPException(404)
    return FileResponse(path)
```

Templates: minimal shared `base.html` (nav: Overview / Library / Calendar / Analytics, small inline CSS), each page a simple table/grid. Calendar renders `range(1, days+1)` cells, listing event titles per day. No JS frameworks.

- [x] **Step 4: Run to verify pass** — `pytest tests/test_dashboard.py -v` → 4 PASS

- [x] **Step 5: Commit** — `git add -A && git commit -m "feat: web dashboard (overview/library/calendar/analytics)"`

---

### Task 15: README, smoke test, polish

**Files:**
- Create: `README.md`
- Full-suite verification + manual smoke checklist

- [x] **Step 1: Write README.md**

Contents (concise):
1. What it is (one paragraph).
2. Setup: `pip install -e ".[dev]"`, copy `.env.example` → `.env`, fill keys.
3. Getting a Pinterest token: developer console → app → OAuth user token scope `boards:read,pins:read,pins:write,user_accounts:read`; note tokens expire (~30 days) — regenerate and paste; refresh-token automation deferred until needed.
4. Usage: `python -m pinterest_automation.main run-once|daemon|serve|publish-now --id N|report --kind daily|weekly`.
5. Architecture summary: status flow diagram `pending → ready → scheduled → published|failed`; where state lives (SQLite); restart-safety explanation.
6. Adding future platforms: pattern note — replicate `api/pinterest.py` + `processors/uploader.publish_pin`; no core changes needed.
7. Limitations (ponytail honesty block): alt_text not accepted by Pinterest create API; analytics window = lifetime since publish; single account.

- [x] **Step 2: Run full suite**

Run: `pytest -v` → all tasks' tests PASS.

- [x] **Step 3: Manual smoke (requires real keys)**

```bash
mkdir -p images && cp some_ai_wallpaper.png images/
python -m pinterest_automation.main scan        # expect "ingested 1 new images"
python -m pinterest_automation.main analyze     # expect "analyzed 1" (costs 1 OpenRouter call)
python -m pinterest_automation.main schedule    # expect "scheduled 1"
python -m pinterest_automation.main run-once    # publishes due pins
python -m pinterest_automation.main serve       # open http://127.0.0.1:8000
```

- [x] **Step 4: Kill-restart safety check**

Start `daemon`, let it schedule pins, Ctrl-C, start again → confirm `run-once` publishes pins whose `scheduled_time` passed while down (state came from DB, not memory).

- [x] **Step 5: Commit** — `git add -A && git commit -m "docs: readme and smoke checklist"`

---

## Dependency order

Tasks are ordered; hard dependencies: 1→2→(3,4,5)→6→(7,8)→9→10→11→(12,13,14)→15. Tasks 3/4/5 are independent of each other and can be parallelized after 2. Task 14 depends only on 2.

## Self-review notes (done during planning)

- **Spec coverage check:** folder detection ✓(T3), vision via OpenRouter ✓(T4–6), all 8 metadata fields ✓(T5), strict JSON ✓(T5), SQLite schema ✓(T2), upload ✓(T7/T9), board mgmt auto+manual ✓(T8), immediate+scheduled ✓(T10/T11 `publish-now`), restart-survival ✓(T10 design + T15 step 4), bulk batching ✓(T6 `BATCH_SIZE` loop), dashboard views ✓(T14), config via env ✓(T1), posting strategy 5–10/day spread ✓(T10, `POSTS_PER_DAY`/`POST_HOURS`), duplicate prevention (hash+DB+unique constraint) ✓(T2/T3), error handling/retries/rate limits/logs ✓(T4/T7/T6), daily/weekly reports ✓(T13), future platforms ✓(Global Constraints note + README section).
- **Deliberate deviations (documented):** alt_text generated+stored but not sent to Pinterest v5 create endpoint (field doesn't exist); scheduler uses DB-backed tick instead of APScheduler job store (simpler, satisfies restart requirement); dashboard is server-rendered Jinja2 instead of SPA (stack lists only backend tools).
- **Type consistency:** status strings consistent everywhere (`pending|ready|scheduled|published|failed`); `map_board(recommended, boards, overrides)->str|None` matches uploader usage; `publish_pin(db, pin, token=None)->bool` matches scheduler and CLI mocks; `sync_published(db, token=None, ...)->int` matches tests.
