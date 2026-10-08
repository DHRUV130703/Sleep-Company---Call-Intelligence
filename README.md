# LimeZip Call Intelligence

Upload sales-call recordings (AI voice bot or human agents) and get transcripts, summaries, buying-intent insights, next actions, and an **AI vs Human** comparison. Everything runs on your machine.

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

## How it fits together

```
Browser (React, :5173) ──/api──▶ API (FastAPI, :8000) ──▶ SQLite (data/app.db) ◀── Worker (python -m app.worker)
                                                         └─ audio files in data/audio/
```

- **API** (`backend/app/main.py`, routes in `backend/app/api/`) answers the web app.
- **Worker** (`backend/app/worker.py`) does the slow work: download → prepare audio → transcribe → analyse. It takes jobs from the `jobs` table, so nothing is lost if it stops. It picks up where it left off.
- **Web app** (`frontend/src/`). There's one file per page in `pages/`, and shared pieces live in `components/`.

## Changing things yourself (no code needed)

| I want to… | Edit | Then |
|---|---|---|
| Change scorecard areas or their descriptions | `config/scorecard.yaml` | Settings → **Reload config** |
| Change intent score ranges, objection types, bot failure patterns | `config/intent_rubric.yaml` | Settings → **Reload config** |
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
  db.py, models.py      database + tables
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
data/                   database + audio (git-ignored)
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
- **The API port is fixed at 8000** (Makefile + Vite proxy) to avoid a setting that would need changing in three places.
