# Pinterest Automation

Automated Pinterest publisher: watches an image folder → generates SEO metadata via OpenRouter vision → stores pins in SQLite → publishes to Pinterest on a schedule → tracks analytics with a small web dashboard.

## Setup

```bash
python3 -m venv venv && ./venv/bin/pip install -e ".[dev]"
cp .env.example .env   # fill in keys
```

### Environment variables (`.env`)

| Variable | Default | Purpose |
|---|---|---|
| `OPENROUTER_API_KEY` | — | OpenRouter API key for vision metadata generation |
| `PINTEREST_ACCESS_TOKEN` | — | Pinterest user access token |
| `PINTEREST_BOARD_ID` | — | Fallback board id when no mapping matches |
| `OPENROUTER_MODEL` | `google/gemini-2.5-flash` | Vision model used for metadata |
| `BATCH_SIZE` | `25` | Pins analyzed per AI call batch |
| `POSTS_PER_DAY` | `5` | Max scheduled posts per day |
| `POST_HOURS` | `8,11,14,17,20` | UTC hours used as posting slots |
| `WATCH_DIR` | `./images` | Folder watched for new images |
| `BOARD_OVERRIDES` | `{}` | JSON map of board name → Pinterest board id, e.g. `{"Couple Wallpapers":"1234567890"}` |

## Pinterest token

1. Create/choose an app at the [Pinterest developer console](https://developers.pinterest.com/).
2. Generate a user token with scopes: `boards:read`, `pins:read`, `pins:write`, `user_accounts:read`.
3. Paste it as `PINTEREST_ACCESS_TOKEN` in `.env`.

Tokens expire (~30 days): regenerate and replace when publishing starts failing auth.
Refresh-token automation is intentionally deferred.

## Usage

```bash
./venv/bin/python -m pinterest_automation.main scan           # ingest new images from WATCH_DIR
./venv/bin/python -m pinterest_automation.main analyze        # generate metadata via OpenRouter
./venv/bin/python -m pinterest_automation.main schedule       # assign future posting slots
./venv/bin/python -m pinterest_automation.main publish-now --id N   # publish one pin immediately
./venv/bin/python -m pinterest_automation.main run-once       # scan + analyze + schedule + publish due
./venv/bin/python -m pinterest_automation.main daemon         # long-running scheduler loop
./venv/bin/python -m pinterest_automation.main serve          # analytics dashboard on :8000
./venv/bin/python -m pinterest_automation.main sync-analytics # refresh metrics for published pins
./venv/bin/python -m pinterest_automation.main report         # daily/weekly summary report
```

## Pipeline states

```
pending ──► ready ──► scheduled ──► published
   │                      │
   └───────(retries)──────┴──► failed        MAX_RETRIES=5 → terminal
```

Schedules live in SQLite, so runs are restart-safe. Failed publishes back off and retry up to `MAX_RETRIES` before the pin becomes permanently failed.

## Adding platforms later

The pattern is one client module (`pinterest_automation/api/<platform>.py`) plus a publish function shaped like `uploader.publish_pin`. Core pipeline (watcher/analyzer/scheduler/DB) stays untouched.

## Limitations

- Alt text is stored locally only — Pinterest v5 create-pin has no alt_text field.
- `post_hours` are UTC.
- Single Pinterest account per instance.
- Analytics window = since each pin's publish date.

## Platform UI (`pinterest-web`)

A Next.js 16 SPA providing drag-drop upload, a Kanban queue, overview stats, and a live activity feed. It talks to the same FastAPI app that serves the legacy analytics dashboard (`serve` on `:8000`).

### Run

```bash
# terminal 1 — backend (serves /api/* and /ws on :8000)
./venv/bin/python -m pinterest_automation.main serve

# terminal 2 — frontend
cd pinterest-web
npm install        # first time only
npm run dev        # http://localhost:3000
```

The frontend expects the API at `NEXT_PUBLIC_API_URL` (default `http://localhost:8000`). CORS allows only `http://localhost:3000`.

### Phase 1 features
- Drag-drop / paste / multi-select upload with SHA-256 duplicate detection.
- Kanban queue: drag pins between **Uploaded (`pending`) / Ready (`ready`) / Scheduled (`scheduled`) / Published (`published`) / Failed (`failed`)**. Only `pending ↔ ready` is a manual move; other transitions are pipeline-driven and return `409`.
- Overview stat cards: totals, per-status counts, clicks / saves / impressions.
- Live activity feed over WebSocket (`/ws`), seeded from recent events and reconnecting with backoff.

### Frontend tests / build

```bash
cd pinterest-web && npm run test && npm run build
```
