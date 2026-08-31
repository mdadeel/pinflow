# PinFlow — Pinterest Automation Platform

**Automate your Pinterest workflow with AI-powered pin generation, scheduling, and CSV bulk upload.**

---

## � quick-start

```bash
# 1. Create and activate a virtual environment
python3 -m venv venv
source venv/bin/activate

# 2. Install the package in development mode
pip install -e ".[dev]"

# 3. Copy the environment file and fill in required keys
cp .env.example .env
# - OPENROUTER_API_KEY: required for AI vision metadata generation
# - PINTEREST_ACCESS_TOKEN: required for publishing to Pinterest
# - PINTEREST_BOARD_ID: fallback board ID

# 4. Start the backend server
./venv/bin/python -m pinterest_automation.main serve

# 5. Start the frontend (separate terminal)
cd pinterest-web
npm install        # first time only
npm run dev        # http://localhost:3000
```

---

## � Environment Variables (`.env`)

| Variable | Required | Default | Purpose |
|---|---|---|---|
| `OPENROUTER_API_KEY` | **yes** | — | API key for AI vision metadata generation via OpenRouter |
| `PINTEREST_ACCESS_TOKEN` | **yes** | — | Pinterest user access token (scopes: `boards:read`, `pins:read`, `pins:write`, `user_accounts:read`) |
| `PINTEREST_BOARD_ID` | no | `` | Fallback board ID when AI category mapping doesn't match |
| `OPENROUTER_MODEL` | no | `google/gemini-2.5-flash` | Vision model used for metadata generation |
| `ANALYSIS_WORKERS` | no | `2` | Number of concurrent LLM calls during analysis |
| `AI_CALL_DELAY_SECONDS` | no | `1.0` | Delay between individual LLM calls (rate-limit protection) |
| `POSTS_PER_DAY` | no | `50` | Maximum pins scheduled per day |
| `POST_HOURS` | no | `8,11,14,17,20` | UTC hours used as posting slots |
| `BATCH_SIZE` | no | `25` | Pins analyzed per AI call batch |
| `WATCH_DIR` | no | `./images` | Folder watched for new images |
| `BOARD_OVERRIDES` | no | `{}` | JSON map of AI category → Pinterest board ID, e.g. `{"Lofi":"1234567890"}` |

### ⚠️ Important: web2api (Gemini Local Sidecar)

The system can operate using only the **Gemini Web2API sidecar** running locally at `http://127.0.0.1:8081`. This sidecar proxies Gemini Vision requests and has no personal API token — it's a local development tool.

**To use Web2API only (no OpenRouter key needed):**

1. Ensure the Gemini Web2API sidecar is running:
   ```bash
   # Start the sidecar (runs at http://127.0.0.1:8081)
   ./venv/bin/python -m pinterest_automation.services.gemini_sidecar
   ```

2. Update `.env` to use only the Web2API provider:
   ```env
   LLM_PROVIDERS=[{"name":"gemini-web2api-local","protocol":"openai","base_url":"http://127.0.0.1:8081/v1/chat/completions","api_key":"sk-gemini-web2api","model":"gemini-3.6-flash","protocol":"openai"}]
   ANALYSIS_WORKERS=1
   AI_CALL_DELAY_SECONDS=1.0
   ```
   
   **Note:** The Gemini API has request quotas. If you see `HTTP 429 Too Many Requests`, you must either:
   - Add credits to Google AI Studio (https://aistudio.google.com/)
   - Add OpenRouter API key back to `.env`
   - Wait for quota reset

3. Run the pipeline:
   ```bash
   ./venv/bin/python -m pinterest_automation.main analyze
   ```

> ⚠️ **Do not commit `.env` or `mini.md`** — these contain API keys and are listed in `.gitignore`. The `mini.md` file holds personal API keys and must never be committed or shared.

---

## � Pinterest API Token

1. Create/choose an app at the [Pinterest developer console](https://developers.pinterest.com/).
2. Generate a user token with scopes: `boards:read`, `pins:read`, `pins:write`, `user_accounts:read`.
3. Paste it as `PINTEREST_ACCESS_TOKEN` in `.env`.
4. Tokens expire (~30 days): regenerate and replace when publishing starts failing auth.

---

## � Usage

```bash
# Scan folder for new images and register in database
./venv/bin/python -m pinterest_automation.main scan

# Generate AI metadata via OpenRouter (or Web2API)
./venv/bin/python -m pinterest_automation.main analyze [--limit N]

# Assign scheduling slots (pins must be status `ready`)
./venv/bin/python -m pinterest_automation.main schedule [--limit N]

# Publish one pin immediately
./venv/bin/python -m pinterest_automation.main publish-now --id 42

# Run one full cycle: scan + analyze + schedule + publish due
./venv/bin/python -m pinterest_automation.main run-once

# Long-running scheduler loop (daemon mode)
./venv/bin/python -m pinterest_automation.main daemon

# Serve analytics dashboard on :8000
./venv/bin/python -m pinterest_automation.main serve

# Sync analytics for published pins
./venv/bin/python -m pinterest_automation.main sync-analytics --days 30

# Generate daily/weekly report
./venv/bin/python -m pinterest_automation.main report --kind daily
```

---

## � Pipeline States

```
pending ────► ready ────► scheduled ────► published
   │              │
   └──────(retries)──────► failed    MAX_RETRIES=5 → terminal
```

- Schedules live in SQLite, so runs are restart-safe.
- Failed publishes back off and retry up to `MAX_RETRIES` before the pin becomes permanently failed.

---

## � Frontend (pinterest-web)

A Next.js 16 SPA providing:
- Drag-drop upload with SHA-256 duplicate detection
- Kanban queue: drag pins between **Uploaded / Ready / Scheduled / Published / Failed**
- Visual calendar scheduler (`/calendar`)
- Analytics center (`/analytics`) with click/save/impression tracking
- Live activity feed over WebSocket (`/ws`)
- Pin editor: review/generate/approve pipeline steps

### Run

```bash
# Terminal 1 — backend (serves /api/* and /ws on :8000)
./venv/bin/python -m pinterest_automation.main serve

# Terminal 2 — frontend
cd pinterest-web
npm run dev        # http://localhost:3000
```

The frontend expects the API at `NEXT_PUBLIC_API_URL` (default `http://localhost:8000`). CORS allows only `http://localhost:3000`.

---

## � AI Provider Configuration

The metadata generator (`analyzer`) calls an LLM. Default is OpenRouter (`OPENROUTER_API_KEY`). To use only the local Web2API sidecar, set `LLM_PROVIDERS` in `.env` as shown above.

Other providers from `mini.md` can be configured via:
- `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL`, `LLM_PROTOCOL`
- `LLM_PROTOCOL` is `openai` (chat/completions) or `anthropic` (messages)

See `.env.example` for the full schema.

---

## � Development & Commands

```bash
# Frontend tests & build
cd pinterest-web && npm run test && npm run build

# Backend pytest
./venv/bin/python -m pytest tests/ -v

# Lint
./venv/bin/python -m ruff check .
```

---

## � Limitations

- Alt text is stored locally only — Pinterest v5 create-pin has no `alt_text` field.
- `post_hours` are UTC.
- Single Pinterest account per instance.
- Analytics window = since each pin's publish date.
- Duplicate detection is via stored SHA-256 `image_hash` (Hamming distance). True perceptual near-duplicate detection would require pHash and is out of scope.

---

## � License

MIT License. See `LICENSE` for details.