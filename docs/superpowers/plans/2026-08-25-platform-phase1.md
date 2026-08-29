# Pinterest Platform — Phase 1 Implementation Plan (Shell, Upload, Queue)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the working automation backend into a platform UI: a Next.js SPA with drag-drop upload, a Kanban image queue with drag-between-columns status moves, overview stats, and a live activity feed — backed by new JSON + WebSocket endpoints on the existing FastAPI app.

**Architecture:** Existing FastAPI app gains `/api/*` JSON routes and a `/ws` broadcast socket fed by a thread-safe in-process event bus that pipeline services already-flow through. New `pinterest-web/` Next.js 15 (App Router, TS, Tailwind, shadcn/ui, zustand, next-themes) talks to those endpoints. The old Jinja dashboard stays served unchanged (replacement happens in later phases). SQLite stays.

**Tech Stack:** FastAPI + SQLAlchemy + Pydantic (existing) · Pillow (new, for image dimensions) · Next.js 15, TypeScript, Tailwind, shadcn/ui, zustand, next-themes, Vitest + Testing Library (all new).

**Spec:** `Pinterest Automation Platform UI & Product Requirements.md` (this repo). Phasing decisions confirmed with user: Next.js SPA; workflow-first phasing; deferred to later phases: AI learning system, vision-based similar-duplicate detection, S3/PostgreSQL, notification center polish.

**Prior build:** `docs/superpowers/plans/2026-08-25-pinterest-publisher.md` (v1 backend — DONE, 92 tests green).

## Global Constraints

- Backend: all new HTTP endpoints under `/api/`; WebSocket at `/ws`. Existing Jinja pages untouched.
- CORS: allow `http://localhost:3000` only (local app).
- No auth (single-user local deployment).
- Image uploads: extensions `.png .jpg .jpeg .webp` (reuse `utils/media_types.py`), max 30 MB/file, saved into `settings.images_dir`, SHA-256 dedup identical to watcher ingest (`status="pending"`).
- Kanban columns map to real statuses: **Uploaded=`pending`, Ready=`ready`, Scheduled=`scheduled`, Published=`published`, Failed=`failed`**. The PRD's 7 columns collapse because `analyzing`/`metadata generated` are transient/pipeline-owned states today; refinement lands with Approval Mode (later phase). Manual drag only permits `pending ↔ ready`; all other transitions are pipeline-driven (409 otherwise).
- All datetimes over the wire: ISO-8601 UTC strings.
- FE: TypeScript strict; App Router; dark/light/system theme via next-themes; state via zustand; no CSS frameworks beyond Tailwind/shadcn; no heavy DnD library (native HTML5 drag events).
- Node 20+ required for `pinterest-web/`.
- Every backend task: pytest TDD. Every FE task: at least one meaningful Vitest/RTL test. Frequent commits.

## File Structure (new files only; existing files modified where noted)

```text
pinterest_automation/
├── database/models.py            # MODIFY: +file_size, +width, +height columns
├── database/db.py                # MODIFY: lightweight ADD COLUMN migration in make_session_factory
├── services/events.py            # NEW: thread-safe event bus + ring buffer + WS subscriber registry
├── api/rest.py                   # NEW: /api routers (uploads, pins, stats)
├── api/ws.py                     # NEW: /ws endpoint
├── main.py                       # MODIFY: include routers, CORS middleware
├── processors/image_watcher.py   # MODIFY: emit event on ingest
├── services/analyzer.py          # MODIFY: emit events on analyzed/failed
├── processors/uploader.py        # MODIFY: emit events on published/failed
pyproject.toml                    # MODIFY: +pillow
tests/
├── test_events.py  test_api_uploads.py  test_api_pins.py  test_api_stats.py  test_api_ws.py  # NEW
pinterest-web/                    # NEW Next.js app (scaffolded in-task)
└── src/app/(pages), src/components/, src/lib/, src/stores/
```

---

### Task 1: Schema extension + lightweight migration + Pillow

**Files:**
- Modify: `pyproject.toml` (add `pillow>=10.4`), `pinterest_automation/database/models.py`, `pinterest_automation/database/db.py`
- Test: `tests/test_db_migration.py`

**Interfaces:**
- Produces: `Pin.file_size: int | None`, `Pin.width: int | None`, `Pin.height: int | None` (nullable Integer). Existing DBs gain the columns automatically on next `make_session_factory` call (ALTER TABLE if missing). `image_dimensions(path) -> tuple[int,int]` helper in `utils/media_types.py`.

- [ ] **Step 1: Write failing test**

`tests/test_db_migration.py`:
```python
import sqlite3


def test_new_columns_exist_on_fresh_db(tmp_path):
    from pinterest_automation.database.db import make_session_factory
    make_session_factory(f"sqlite:///{tmp_path}/t.db")
    con = sqlite3.connect(tmp_path / "t.db")
    cols = {r[1] for r in con.execute("PRAGMA table_info(pins)")}
    assert {"file_size", "width", "height"} <= cols


def test_migration_adds_columns_to_old_db(tmp_path):
    import sqlite3

    from pinterest_automation.database.db import make_session_factory
    p = tmp_path / "old.db"
    con = sqlite3.connect(p)
    con.execute("""CREATE TABLE pins (
        id INTEGER PRIMARY KEY,
        image_path VARCHAR(500),
        image_hash VARCHAR(64))""")
    con.commit(); con.close()
    make_session_factory(f"sqlite:///{p}")     # must not crash; adds missing columns
    con = sqlite3.connect(p)
    cols = {r[1] for r in con.execute("PRAGMA table_info(pins)")}
    assert {"file_size", "width", "height"} <= cols
    # NOTE: full legacy schema has many more NOT NULL columns; the migration must be
    # tolerant — implement by checking PRAGMA table_info and ALTER TABLE ADD COLUMN
    # per missing tracked column, ignoring failures for columns whose context is gone.


def test_image_dimensions_png(tmp_path):
    from PIL import Image
    from pinterest_automation.utils.media_types import image_dimensions
    img = Image.new("RGB", (640, 360))
    p = tmp_path / "a.png"
    img.save(p)
    assert image_dimensions(p) == (640, 360)


def test_pin_roundtrip_with_size_fields(Session=None):
    from pinterest_automation.database.db import make_session_factory
    from pinterest_automation.database.models import Pin
    import tempfile, os
    with tempfile.TemporaryDirectory() as d:
        f = make_session_factory(f"sqlite:///{d}/t.db")
        with f() as s:
            s.add(Pin(image_path="/x.png", image_hash="h", file_size=123, width=800, height=600))
            s.commit()
            row = s.query(Pin).one()
            assert (row.file_size, row.width, row.height) == (123, 800, 600)
```
(Finalize signatures cleanly — the `Session=None` oddity above is placeholder noise; write it as a plain tmp_path fixture test like the others.)

- [ ] **Step 2: Run to verify fail** — `./venv/bin/pytest tests/test_db_migration.py -v` → FAIL

- [ ] **Step 3: Implement**
- pyproject dependencies += `"pillow>=10.4"`, then `./venv/bin/pip install -e ".[dev]"`.
- `models.py`: three nullable Integer columns appended to Pin.
- `db.py`: after `Base.metadata.create_all(engine)` inside `make_session_factory`, run `_ensure_pin_columns(engine)`:
```python
from sqlalchemy import text

TRACKED_PIN_COLUMNS = {"file_size": "INTEGER", "width": "INTEGER", "height": "INTEGER"}

def _ensure_pin_columns(engine) -> None:
    existing = {row[1] for row in engine.connect().exec_driver_sql("PRAGMA table_info(pins)")}
    for name, ddl in TRACKED_PIN_COLUMNS.items():
        if name not in existing:
            with engine.begin() as conn:
                conn.exec_driver_sql(f"ALTER TABLE pins ADD COLUMN {name} {ddl}")
```
(On a brand-new DB `create_all` already made them; the helper no-ops. On legacy partial DBs it patches what it can.)
- `utils/media_types.py` += :
```python
from PIL import Image

def image_dimensions(path):
    with Image.open(path) as im:
        return im.size
```

- [ ] **Step 4: Run to verify pass** — full suite green (92 + new).
- [ ] **Step 5: Commit** — `git add` explicit; message `feat: pin size/dimension columns with auto migration`

---

### Task 2: Event bus + service instrumentation

**Files:**
- Create: `pinterest_automation/services/events.py`
- Modify: `processors/image_watcher.py`, `services/analyzer.py`, `processors/uploader.py`, `services/scheduler.py` (emit only)
- Test: `tests/test_events.py`

**Interfaces:**
- Produces:
  - `subscribe() -> queue.Queue` — returns a registered queue (thread-safe registry).
  - `unsubscribe(q) -> None`
  - `recent_events(limit=50) -> list[dict]`
  - `publish(event_type: str, **payload) -> dict` — builds `{"type", "payload", "at"(ISO UTC)}`, appends to 200-entry ring buffer, puts onto every subscriber queue (safe from any thread; never raises to caller).
  - Event types emitted by services: `image.uploaded`(path,filename), `metadata.generated`(pin_id,title), `metadata.failed`(pin_id,error), `pin.scheduled`(pin_id,scheduled_time), `pin.published`(pin_id,pin_url), `publish.failed`(pin_id,error).

- [ ] **Step 1: Write failing test**
```python
import queue


def test_publish_delivers_to_subscribers_and_buffer():
    from pinterest_automation.services import events
    q = events.subscribe()
    try:
        evt = events.publish("pin.published", pin_id=7)
        assert evt["type"] == "pin.published" and evt["payload"]["pin_id"] == 7
        assert q.get_nowait() == evt
        assert evt in events.recent_events()
    finally:
        events.unsubscribe(q)


def test_unsubscribe_stops_delivery():
    from pinterest_automation.services import events
    q = events.subscribe()
    events.unsubscribe(q)
    events.publish("image.uploaded", path="/x.png")
    assert q.empty()


def test_publish_never_raises_to_caller():
    from pinterest_automation.services import events
    class BadQueue(queue.Queue):
        def put_nowait(self, item): raise RuntimeError("boom")
    bad = events.subscribe.__wrapped__() if hasattr(events.subscribe, "__wrapped__") else None
    # simpler: monkeypatch registry with a broken queue object
    import unittest.mock as mock
    with mock.patch.object(events, "_subs", [BadQueue()]):
        events.publish("pin.scheduled", pin_id=1)   # must not raise
```
(Clean up the half-written lines — test only the mock.patch variant.)

- [ ] **Step 2: Verify fail** → implement `events.py`:
```python
import logging
import queue
import threading
from collections import deque

from pinterest_automation.database.db import utcnow

log = logging.getLogger(__name__)
_subs: list = []
_lock = threading.Lock()
_recent: deque = deque(maxlen=200)


def subscribe():
    q = queue.Queue()
    with _lock:
        _subs.append(q)
    return q


def unsubscribe(q) -> None:
    with _lock:
        if q in _subs:
            _subs.remove(q)


def recent_events(limit: int = 50) -> list:
    with _lock:
        return list(_recent)[-limit:]


def publish(event_type: str, **payload) -> dict:
    evt = {"type": event_type, "payload": payload, "at": utcnow().isoformat()}
    with _lock:
        _recent.append(evt)
        subs = list(_subs)
    for q in subs:
        try:
            q.put_nowait(evt)
        except Exception:  # noqa: BLE001 - a dead subscriber must not break publishers
            log.warning("event subscriber dropped")
    log.info("event %s %s", event_type, payload)
    return evt
```
Then instrument (one-line publishes at the success/failure points listed above — watcher after commit, analyzer in `_apply`/except, uploader in success/both failure paths, scheduler in assign loop).

- [ ] **Step 3: Full suite green** (existing tests unaffected; events fire harmlessly).
- [ ] **Step 4: Commit** — `feat: in-process event bus with pipeline instrumentation`

---

### Task 3: Upload REST endpoint

**Files:**
- Create: `pinterest_automation/api/rest.py`, `tests/test_api_uploads.py`

**Interfaces:**
- `POST /api/uploads` (multipart `files: list[UploadFile]`) → `201 {"added": [PinOut], "duplicates": [filenames], "rejected": [{"filename","reason"}]}`
- `PinOut` schema (api/rest.py): `{id, filename, image_url:"/media/{id}", status, title, description, alt_text, primary_keyword, secondary_keywords(list|null), tags(list|null), board_name, content_category, file_size, width, height, created_at}`
- Saves valid files into `settings.images_dir` (mkdir ok), SHA-256 dedup against DB (duplicate filenames reported, not inserted), records file_size + dimensions, inserts `pending` Pin rows, emits `image.uploaded` per added file.

- [ ] **Step 1: Failing tests** (TestClient + tmp factory fixture like test_dashboard; craft a tiny real PNG with Pillow; assert added/duplicate/rejected buckets, dedup second call, DB row fields, event emitted)
- [ ] **Step 2: verify fail**
- [ ] **Step 3: Implement** — `rest.py` with `router = APIRouter(prefix="/api")`; Pydantic `PinOut.model_validate` from ORM (`model_config = ConfigDict(from_attributes=True)`); streaming copy `shutil.copyfileobj` to dest with 30 MB guard; reuse `sha256_file`, `EXTENSIONS`, `image_dimensions`; collision-safe naming (`name (1).png` suffix loop).
- [ ] **Step 4: pass** → **Step 5: Commit** — `feat: /api/uploads with dedup and metadata capture`

---

### Task 4: Pins REST (list/detail/manual status move)

**Files:**
- Create: rest additions in `api/rest.py`, `tests/test_api_pins.py`

**Interfaces:**
- `GET /api/pins?status=&page=1&per_page=50&q=` → `{items:[PinOut], total, page, per_page}` (`q` searches title/board_name/content_category/primary_keyword LIKE)
- `GET /api/pins/{id}` → PinOut | 404
- `PATCH /api/pins/{id}/status` body `{"status":"ready"}` — ONLY manual transitions `pending↔ready` allowed; else `409 {"detail": ...}`; unknown status → 422; missing pin → 404; emits `pin.updated` event on change.

- [ ] Steps: failing tests (filter, search, pagination totals, both allowed moves, rejected move 409, 404) → implement → pass → commit `feat: pins rest api with guarded manual transitions`

---

### Task 5: Stats endpoint

**Files:** rest additions, `tests/test_api_stats.py`
- `GET /api/stats` → `{"total", "pending", "ready", "scheduled", "published", "failed", "impressions", "clicks", "saves", "outbound_clicks"}` (counts by status; analytics sums coalesced to 0).
- [ ] failing test → implement (two queries) → pass → commit `feat: /api/stats overview metrics`

---

### Task 6: WebSocket + CORS wiring

**Files:**
- Create: `pinterest_automation/api/ws.py`, `tests/test_api_ws.py`
- Modify: `main.py` (include routers; CORSMiddleware allow `http://localhost:3000`)

**Interfaces:**
- `WS /ws`: on connect sends `{"type":"hello","payload":{"recent":[...last 50...]}}`, then streams live events; disconnect cleans up subscription. Publishing threads → queues → this async loop reads `queue.Queue` via `anyio.to_thread`/polling pattern: simplest correct = `await asyncio.get_running_loop().run_in_executor(None, q.get, True, 1.0)` timeout loop checking `ws.client_state`.
- [ ] failing test: TestClient `websocket_connect` receives hello w/ recent buffer; two clients both receive a subsequent `publish()`; disconnect unregisters → implement → pass → commit `feat: /ws event stream and cors`

---

### Task 7: Next.js scaffold + app shell + dark mode

**Files:**
- Create: `pinterest-web/**` (create-next-app: TS, ESLint, Tailwind, App Router, src dir, npm), shadcn init + Button/Card/DropdownMenu components, `src/components/theme-provider.tsx`, nav shell in `src/app/layout.tsx`, placeholder `/` `/upload` `/queue` pages, `.gitignore` entry `pinterest-web/node_modules` etc. (root .gitignore append)
- Test: `pinterest-web/src/lib/__tests__/api.test.ts` (Vitest) + component render test for nav

**Interfaces (consumed by Tasks 8–10):**
- `src/lib/api.ts`: typed client — `fetchPins(params)`, `fetchStats()`, `movePin(id,status)`, `uploadFiles(files)` hitting `NEXT_PUBLIC_API_URL ?? http://localhost:8000`; shared `Pin` type mirroring PinOut.
- `ThemeToggle` (light/dark/system) persisted via next-themes.

- [ ] Scaffold steps: `node -v` guard (≥20) → create-next-app → `npx shadcn@latest init -d` → add components → install `zustand next-themes` + dev `vitest @testing-library/react jsdom @vitejs/plugin-react` → vitest config → nav shell (brand, links Overview/Upload/Queue, ThemeToggle) → tests → `npm run build` passes → root commit (exclude node_modules/.next via gitignore).

---

### Task 8: FE Upload page (drag-drop/paste/multi)

**Files:** `pinterest-web/src/app/upload/page.tsx`, `src/components/upload-zone.tsx`, store slice; RTL test for drop-handler calling uploadFiles + result rendering.

Behavior: full-page dropzone (dragover highlight), folder drops via `DataTransferItem.webkitGetAsEntry` recursion (best-effort), clipboard paste listener, multi-select button fallback; after upload → grid of uploaded thumbnails (filename, dimensions, size; `/media/{id}` for preview) + duplicates/rejected notices.

- [ ] failing RTL test → implement (component + zustand `useUploadStore`) → vitest green + `npm run build` → commit `feat(web): drag-drop upload zone`

---

### Task 9: FE Queue Kanban board

**Files:** `pinterest-web/src/app/queue/page.tsx`, `src/components/kanban-board.tsx`, `src/stores/queue-store.ts`, RTL test for move logic + optimistic reorder.

Columns: the five statuses (Global Constraints mapping). Card: thumbnail, status chip, category, scheduled date (if any), board. Native HTML5 DnD: card `draggable` + `onDragStart` sets id; column `onDragOver preventDefault` + `onDrop` → `movePin`; optimistic store update, revert on API error (toast-less inline banner fine for P1). Refresh button + auto-refetch every 30 s (WS-driven live updates come with Task 10's feed; queue polling is fine).

- [ ] failing store/component test → implement → green + build → commit `feat(web): kanban image queue with drag status moves`

---

### Task 10: FE Overview (stats cards + live activity feed)

**Files:** `pinterest-web/src/app/page.tsx`, `src/components/stat-cards.tsx`, `src/components/activity-feed.tsx`, hook `src/hooks/use-event-stream.ts` (WebSocket connect to `NEXT_PUBLIC_API_URL`/ws, reconnect w/ backoff, seed from hello.recent), tests for reducer/hook logic.

Cards: Total Images, Pending, AI Generated (=ready), Scheduled, Published, Failed, Clicks, Saves, Impressions (from `/api/stats`). Feed renders newest-first event rows with relative time.

- [ ] failing tests → implement → green + build → commit `feat(web): overview dashboard with live activity feed`

---

### Task 11: Verification + README/platform notes

- [ ] Run backend suite (`./venv/bin/pytest -v`) AND frontend (`cd pinterest-web && npm run test && npm run build`)
- [ ] Two-terminal smoke: uvicorn app + `npm run dev`; walk the checklist: upload 2 pngs (one duplicate) → appears in queue Uploaded; drag to Ready → PATCH visible in DB; stats cards reflect counts; activity feed shows upload + move events live; dark mode toggles; calendar/library Jinja pages still work
- [ ] README: add "Platform UI" section (run web: `cd pinterest-web && npm run dev`; env vars NEXT_PUBLIC_API_URL)
- [ ] Commit `docs: phase 1 platform verification`

## Self-review (done during planning)

- **PRD coverage for Phase 1:** statistics cards ✓(T5/T10 incl clicks/saves/impressions), activity feed real-time ✓(T2/T6/T10), drag-drop upload area w/ folder/paste/multi + thumb/name/resolution/size ✓(T3/T8), Kanban queue w/ drag ✓(T4/T9, 5-column mapping documented), dark/light/system ✓(T7). Explicitly OUT (later phases per user): editor workspace/regen options, visual scheduler, publishing center, analytics center, costs, history, search, templates, notifications, quality score, approval, one-click, AI learning, vision-duplicates, Postgres/S3.
- **Deviations documented:** 5-column kanban (PRD 7), queue polling + WS feed (full WS-driven queue sync later), best-effort folder drop (webkitGetAsEntry).
- **Consistency:** PinOut field names match model columns; status vocabulary identical to v1; `/media/{id}` reused for FE thumbnails.
