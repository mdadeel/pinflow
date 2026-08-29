# Pinterest Platform — Phase 2 Implementation Plan (Editor → Scheduler → Analytics → AI)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Make the platform usable end-to-end. Phase 1 gave upload + queue + live feed but (a) AI metadata was uneditable, and (b) `ready→scheduled` was blocked (409), so pins never entered the publishing pipeline from the UI. Phase 2 adds: a pin Editor (view/edit metadata, regenerate, approve-to-schedule), a visual calendar/scheduler, an analytics center, and AI enhancements (vision duplicate detection + learning from edits).

**Architecture:** Same FastAPI app (`pinterest_automation/api/*`) + same `pinterest-web/` Next.js 16 SPA. SQLite stays. No new runtime deps where avoidable (hand-roll charts/hashes with PIL to respect ponytail).

**Sequencing (user chose "all in order"):** 2a → 2b → 2c → 2d. Each sub-phase keeps the same quality bar: backend pytest TDD, frontend vitest + `npm run build`, explicit commits, two-stage verification.

**Global Constraints (carried from Phase 1):** all new endpoints under `/api/`; CORS `http://localhost:3000`; no auth; ISO-8601 UTC over the wire; FE TS strict; native HTML5 DnD only (no heavy DnD lib); no new npm packages unless explicitly noted; backend TDD per task; frequent commits.

---

## Phase 2a — Editor Workspace + Approval

**Backend**

### T2a.1: Editable metadata `PATCH /api/pins/{id}` + add schedule/publish times to PinOut
- Files: `pinterest_automation/api/rest.py` (modify PinOut + add PATCH), `tests/test_api_edit.py`
- PinOut gains `scheduled_time: str | None`, `published_time: str | None` (ISO from model datetimes).
- `PATCH /api/pins/{id}` body `PinEdit` (all optional): `title, description, alt_text, primary_keyword, secondary_keywords (list[str]), tags (list[str]), board_name, content_category`.
  - Editable only when status in `pending`/`ready` (published/failed → 409 "pin is {status}, not editable"). Missing pin → 404.
  - Persists: `secondary_keywords`/`tags` stored as JSON strings (reuse `_to_pin_out` _list logic inverted). Emits `metadata.edited` (pin_id, fields).
- Tests: edit round-trips; published pin edit → 409; 404; scheduled_time/published_time present in PinOut when set.

### T2a.2: Regenerate metadata `POST /api/pins/{id}/regenerate`
- Files: `pinterest_automation/services/analyzer.py` (add `regenerate_pin(db, pin_id) -> Pin | None`), `pinterest_automation/api/rest.py` (endpoint), `tests/test_api_regenerate.py`
- `regenerate_pin`: re-runs `generate_metadata(Path(pin.image_path))`, applies via `_apply` (sets status `ready`, ai_called_at), commits, returns pin. Image missing → raises (endpoint → 422/409). Emits `metadata.generated`.
- Tests: pending/ready pin regenerates to `ready` with new title; missing image → error; 404 for bad id.

### T2a.3: Approve `POST /api/pins/{id}/approve`
- Files: `pinterest_automation/api/rest.py` (endpoint), `tests/test_api_approve.py`
- Calls `scheduler.assign_schedule_times(db, [pin_id])`. Only valid from `ready` (pending must go →ready first; else 409 "approve requires ready"). Returns PinOut with `scheduled_time` set; status `scheduled`. Emits `pin.scheduled`.
- Tests: ready→approve sets scheduled_time + status scheduled; pending→approve 409; 404.

**Frontend**

### T2a.4: Editor route `/pin/[id]`
- Files: `pinterest-web/src/app/pin/[id]/page.tsx` (new, client), `pinterest-web/src/components/pin-editor.tsx` (new), store optional.
- Loads pin via `fetchPin(id)` (add `fetchPin` to api.ts). Shows thumbnail (`API_BASE+image_url`), editable fields (title, description, alt_text, primary_keyword, secondary_keywords, tags, board_name, content_category), Save (PATCH), Regenerate, Approve buttons. Optimistic-free; show inline error banner on API error (e.g. 409).
- api.ts additions: `fetchPin(id)`, `updatePin(id, PinEdit)`, `regeneratePin(id)`, `approvePin(id)`; add `PinEdit` type; add `scheduled_time`/`published_time` to `Pin`.

### T2a.5: Wire editor into queue + overview
- Files: `pinterest-web/src/components/kanban-board.tsx` (card click → router push `/pin/{id}`), `pinterest-web/src/components/activity-feed.tsx` (event label for `metadata.edited`/`pin.scheduled`).
- Tests: kanban card click navigates (mock next/navigation); editor save calls updatePin and reflects value.

### T2a.6: Verify + commit
- `npm run test` + `npm run build` green. Commit `feat(web): pin editor with edit/regenerate/approve`.

---

## Phase 2b — Visual Scheduler / Calendar

### T2b.1: Reschedule endpoint `PATCH /api/pins/{id}/schedule`
- Files: `pinterest_automation/api/rest.py`, `tests/test_api_reschedule.py`
- Body `{scheduled_time: ISO}` → sets `pin.scheduled_time`, status→`scheduled` (only from `ready`/`scheduled`; published/failed → 409). Emits `pin.scheduled`. (Approval still the primary path; this refines an already-scheduled pin.)

### T2b.2: Calendar page `/calendar`
- Files: `pinterest-web/src/app/calendar/page.tsx` (new), `pinterest-web/src/components/calendar-grid.tsx` (new), `pinterest-web/src/hooks/use-pins.ts` (optional list hook).
- Month grid; fetch scheduled + published pins (add `fetchByStatuses` or reuse `fetchPins` per status) and place on their `scheduled_time`/`published_time` day. Click day/pin → editor. Drag a scheduled pin to another day → `approvePin`/reschedule PATCH.
- Tests: grid renders pins on correct day; drag to new day calls reschedule.

### T2b.3: Verify + commit `feat(web): visual calendar scheduler`.

---

## Phase 2c — Analytics Center

### T2c.1: Analytics summary `GET /api/analytics`
- Files: `pinterest_automation/api/rest.py`, `tests/test_api_analytics.py`
- Returns `{ totals:{...}, by_status:{...}, top_pins:[{id,title,clicks,saves,impressions,ctr}], series:[{date,impressions,clicks,saves}] (last 30d), ctr }`. Reuse reporting aggregates.

### T2c.2: Analytics page `/analytics`
- Files: `pinterest-web/src/app/analytics/page.tsx` (new), `pinterest-web/src/components/charts.tsx` (hand-rolled SVG/CSS bar+sparkline, no new dep), `pinterest-web/src/lib/api.ts` (+`fetchAnalytics`, `Analytics` type).
- Stat cards + per-status donut (CSS) + top-pins table + 30d impressions/clicks sparkline (SVG).

### T2c.3: Verify + commit `feat(web): analytics center`.

---

## Phase 2d — AI Enhancements

### T2d.1: Vision duplicate detection (hand-rolled, no dep)
- Files: `pinterest_automation/utils/perceptual_hash.py` (new, PIL average-hash), `pinterest_automation/api/rest.py` (upload flags `similar_to`), `tests/test_perceptual_hash.py`.
- On upload, compute average hash of new image; compare to existing pins' hashes (store `image_hash` is SHA-256 content hash already; add `phash` column? ponytail: store phash on Pin to avoid recompute). New column `phash TEXT` via migration (extend T1 migration helper). Upload response `added[].similar_to: [ids]` when hamming distance ≤ threshold.
- Tests: identical image → similar_to non-empty; different → empty.

### T2d.2: Learn from edits (light)
- Files: `pinterest_automation/services/learning.py` (new: record board/category corrections, expose defaults), instrument editor save to log corrections, `seo_generator` consults learned defaults as hints (optional, minimal).
- Tests: correction recorded; regenerate applies learned board default.

### T2d.3: Verify + commit `feat: vision duplicate detection + edit learning`.

---

## Phase 2 verification
- Backend `./venv/bin/pytest -v` + frontend `npm run test && npm run build` both green.
- Smoke: serve + dev; walk editor→regenerate→approve→calendar→analytics; README "Platform UI" section updated with new routes/env notes.
- Commit `docs: phase 2 platform verification`.
