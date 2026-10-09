# LimeZip Call Intelligence

Upload sales-call recordings (AI voice bot or human agents) and get transcripts, summaries, buying-intent insights, next actions, and an **AI vs Human** comparison. The app runs on your machine; data and recordings are stored in a cloud database (CockroachDB).

- What we're building and why: [PRD.md](PRD.md)
- Rules for the coding agent: [CLAUDE.md](CLAUDE.md)

## Requirements

| Tool | Install (macOS) |
|---|---|
| [uv](https://docs.astral.sh/uv/) (Python manager; installs Python 3.12 for you) | `brew install uv` |
| Node.js 20+ | `brew install node` |
| ffmpeg | `brew install ffmpeg` |

## First run

```bash
make setup      # installs everything, creates .env and the database
make dev        # starts the API, the worker and the web app
```

Open **http://localhost:5173**. Settings → *System health* shows whether everything is ready.

Everything runs locally by default — **no API keys**:
- **Speech-to-text:** Whisper on your Mac (Apple Silicon, `mlx-whisper`). The model (~1.6 GB) downloads once.
- **Analysis:** your logged-in Claude via the `claude` command (Claude Code). Log in once:

```bash
claude auth login
```

(Optional cloud providers — OpenAI / Gemini — can be switched on in `.env`.)

## Everyday commands

| Command | What it does |
|---|---|
| `make dev` | Run everything (Ctrl+C stops all three) |
| `make test` | Backend + frontend tests |
| `make lint` | Code checks |
| `make format` | Auto-format backend code |
| `make migrate` | Apply database changes |
| `make migration name="…"` | Create a database change after editing `backend/app/models.py` |
| `make export-sqlite` | Export report data (calls, scores, transcripts, AI vs Human plan) to `exports/limezip-reports-<date>.db` — open with `sqlite3` or DB Browser for SQLite |
| *(no command)* | In the cloud database's SQL console the same report tables exist as live views (`verdict`, `improvement_plan`, `call_scores`, `calls_report`, `call_rca_issues`, … — see `backend/app/report_views.sql`) |
| `make move-to-cloud` | One time: copy the local `data/` folder (database + files) into the cloud database in `DATABASE_URL` |

## How it fits together

```
Browser (React, :5173) ──/api──▶ API (FastAPI, :8000) ──▶ Cloud database (CockroachDB) ◀── Worker (python -m app.worker)
                                                          tables + every file: recordings,
                                                          uploads, spreadsheets, raw transcripts
```

- **Storage:** with `DATABASE_URL` set in `.env`, everything lives in the cloud database — nothing is kept on
  this computer. Files are stored in the `blobs` / `blob_parts` tables in 1 MB parts (`backend/app/storage.py`);
  ffmpeg and the speech-to-text APIs get a temporary copy that is deleted straight after. Without
  `DATABASE_URL` the same code uses a local SQLite file in `data/`.
- **Moving a local install to the cloud (one time):** set `DATABASE_URL`, then `make move-to-cloud`. It copies
  every row and file from `data/` and leaves `data/` untouched as a backup.

- **API** (`backend/app/main.py`, routes in `backend/app/api/`) answers the web app.
- **Worker** (`backend/app/worker.py`) does the slow work: download → prepare audio → transcribe → analyse. It takes jobs from the `jobs` table, so nothing is lost if it stops. It picks up where it left off.
- **Web app** (`frontend/src/`). There's one file per page in `pages/`, and shared pieces live in `components/`.

## Changing things yourself (no code needed)

| I want to… | Edit | Then |
|---|---|---|
| Change scorecard areas or their descriptions | `config/scorecard.yaml` | Settings → **Reload config** |
| Change intent score ranges, objection types, bot failure patterns | `config/intent_rubric.yaml` | Settings → **Reload config** |
| Change how bot fixes are ranked, who owns each fix, and the suggested fix | `config/bot_playbook.yaml` | Settings → **Reload config**, then **Re-run comparison** |
| Switch AI provider or model, change concurrency, limits, privacy | `.env` | restart `make dev` |
| Change colours or fonts | `frontend/src/styles/tokens.css` | saved = live |
| Change the workspace name in the sidebar | `frontend/src/lib/constants.ts` | saved = live |
| Change what the AI is asked (from M2/M3) | `backend/app/prompts/*.md` | re-analyse calls |

## Project layout

```
config/                 business rules (YAML) — safe to edit
backend/app/
  main.py               FastAPI app
  config.py             reads .env and config/*.yaml
  db.py, models.py      database + tables (CockroachDB in the cloud, or local SQLite)
  storage.py            files (recordings, uploads, sheets) stored in the database
  errors.py             error codes + the messages users see
  worker.py             background job loop
  api/                  HTTP endpoints, one file per area
  ingest/               upload, ZIP, spreadsheet, link download   (M1)
  pipeline/             stages, audio, metrics, grounding, compare (M2–M5)
  providers/            Gemini / Claude / Whisper adapters         (M2–M3)
  prompts/              AI prompt templates                        (M2–M3)
backend/tests/          pytest
frontend/src/
  pages/                one file per screen
  components/           shared UI (layout/, ui/ = shadcn primitives)
  lib/                  api client, formatting, theme, types
  styles/tokens.css     design tokens (colours, radii)
data/                   local SQLite mode only (git-ignored); unused when DATABASE_URL is set
```

## Build progress

| Milestone | Status |
|---|---|
| M0 Skeleton: app shell, health, settings, DB schema, worker loop | ✅ done |
| M1 Uploader and ingest (spreadsheet / ZIP / files / links, resumable chunks) | ✅ done |
| M2 Pipeline and live progress (SSE) | ✅ done |
| M3 Per-call analysis and Call Detail | ✅ done |
| M4 Leads list and Lead Details | ✅ done |
| M5 AI vs Human | ✅ done |
| M6 Polish (Docker, eval set, PDF export) | partly — see Decisions |

## Decisions

Choices made during the build where the PRD left room. Each one is easy to revisit.

- **Python 3.12 via uv.** `uv sync` installs the exact versions in `backend/uv.lock`. There's no `.python-version` file, because it confuses pyenv; `pyproject.toml` pins 3.12.
- **oxlint instead of eslint.** It's the current Vite template default, much faster, and the same rules matter.
- **`GET /api/stats`** was added (not in the PRD API table) for the sidebar footer: last processed time and total audio processed.
- **Worker heartbeat** is a file (`data/worker.heartbeat`) rather than a table, which is the simplest thing that works. `/api/health` treats the worker as down after 20 s of silence.
- **Health states**: a missing API key is a *warning*, not a failure, so the app is usable for setup before keys exist.
- **Times** are stored as UTC and always returned with a timezone (`UTCDateTime` in `db.py`).
- **Fonts** are self-hosted (Inter, JetBrains Mono via Fontsource), so the app works offline.
- **Providers (07 Oct 2026):** transcription uses OpenAI `gpt-4o-transcribe-diarize`, because it labels speakers and plain `whisper-1` doesn't. Analysis uses Gemini (`gemini-3.8-flash`), since there's no Anthropic key. Gemini transcription (`gemini-3.5-transcribe`) stays available to A/B test on real Hinglish calls in M2. Every model is a `.env` setting.
- **Tests never read `.env`**, so real API keys can't leak into or be spent by the test suite.
- **Fully local AI (07 Oct 2026, by request):** Whisper (mlx-whisper, `whisper-large-v3-turbo`) transcribes each spoken turn separately so English and Hindi lines each keep their language; Claude (local `claude` CLI, `--json-schema` structured output, no tools) labels agent/customer, rewrites Hindi in Roman Hinglish, and does all analysis. OpenAI/Gemini providers remain available in `.env` but are off.
- **Dialer file names** (Ameyo: `agent__campaign__…__phone__date_time.mp3`) fill in agent, campaign and call time automatically.
- **One lead per phone number**; several recordings of the same number are stacked under that lead.
- **Tables use server-side paging** (25–50 rows) instead of virtualisation — simpler, and fast enough.
- **Not built yet:** Docker compose, labelled eval set (`make eval`), PDF export, app passcode, stereo channel-based speaker split.
- **Cloud database, no local disk:** the database is CockroachDB (Postgres-compatible, `DATABASE_URL`). Files are stored in the same database as 1 MB parts instead of a separate object store, at the user's request ("move all data to the db") — one service, one bill, nothing on the local disk. Trade-off: a few MB/s per file, fine for call recordings (~0.25 MB/min). New dependencies, needed to talk to CockroachDB: `sqlalchemy-cockroachdb` (its dialect), `psycopg[binary]` (driver), `certifi` (CA certificates to verify the server's TLS). Connections use READ COMMITTED isolation (the API and the worker write at the same time without retry errors) and sequential ids (CockroachDB's default random 64-bit ids are too large for JavaScript). Uploaded 8 MB chunks are joined by re-labelling their parts in SQL, without copying bytes. Worker heartbeat moved to the `worker_heartbeats` table; the single-worker lock file lives in the system temp folder.
- **Bot improvement plan (AI vs Human):** the verdict, ranked improvement parameters, root causes, missed objections and call-by-call RCA are computed in code (`pipeline/bot_improvement.py`, `pipeline/bot_rca.py`), so they are complete even when the AI-written summary hits a rate limit. Priority = gap to the human average OR how often the bot is weak (score 1–2), thresholds in `config/bot_playbook.yaml`. The verdict is "behind" if quality is > 0.3 below humans **or** the bot ends ≥ 10 points fewer calls with a concrete next step. Each weak moment carries a "better" line written during the per-call analysis (prompt v3); calls reviewed with an older prompt can be refreshed with **Update bot reviews** on the page. The AI summary prompt is capped (~5,000 characters of call digests, worst bot calls and best human calls first) to fit Groq's free tier.
- **AI vs Human page layout:** one summary card (verdict, scores, key points, and a one-line "based on" note that replaced the Records section), then three tabs — *What to fix* (default), *Calls*, *Side by side* — instead of 12 stacked sections and an "On this page" list. The open tab is kept in the URL (`?view=`). Downloads only (no share-link UI); the server still keeps each downloaded file in `reports`.
- **Worker on a metered cloud database:** idle job slots don't query the database. One cheap check every 5 s wakes them when work is queued, and finishing a stage wakes them for the next one; heartbeat every 15 s. Before, 10 slots polling every second kept the free CockroachDB tier throttled. Database hiccups no longer stop the worker — it waits and retries.
- **Saved reports with public links:** every AI vs Human download (PDF, Word, Excel, CSV, JSON) is also stored in the database (file in `blobs`, a row in `reports` with its public `url`), and the same report build is never made twice. Links look like `<PUBLIC_BASE_URL>/api/reports/<random token>/<file>` — unguessable, no login (like a shared Google Docs link). `PUBLIC_BASE_URL` defaults to `http://localhost:5173`, so links only open on this computer until the app is deployed. PDFs are now made on the server with `fpdf2` + `uharfbuzz` (HarfBuzz text shaping) and bundled Noto fonts (`backend/app/fonts`, SIL Open Font License), so Hindi renders correctly without a browser. New dependencies at the user's request: `fpdf2`, `uharfbuzz`.
- **Shareable AI vs Human report (Word + PDF):** both are rendered from one outline (`backend/app/pipeline/report.py`), so they always match. Word uses `python-docx` (new dependency, added at the user's request). The PDF is the browser's "Save as PDF" of a print-ready page, because server-side PDF libraries render Hindi (Devanagari) incorrectly without extra font files.
- **The API port is fixed at 8000** (Makefile + Vite proxy) to avoid a setting that would need changing in three places.
