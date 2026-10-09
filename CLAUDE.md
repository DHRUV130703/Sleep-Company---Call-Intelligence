# CLAUDE.md — Build instructions for LimeZip Call Intelligence

Read `PRD.md` first. It is the source of truth for **what** to build. This file says **how** to build it.

## Mission
Build a local call-intelligence app: upload call recordings (ZIP / Excel of links / direct links) → transcribe → summarise → insights and next actions → **AI voice bot vs Human agents** comparison. The UI copies the layouts in PRD §6 and §9 using our own branding.

## Golden rules
1. **Simple over clever.** The owner must be able to read and change this code without AI help. Prefer plain functions, explicit names and short files (< 300 lines). No metaprogramming, no deep class hierarchies, no "frameworks inside the framework".
2. **Stick to the stack in PRD §8.1.** Don't add a dependency that isn't listed there without stating why in your message and getting approval. No Redis, Celery, Kafka, ORMs other than SQLModel, or state libraries other than TanStack Query and React state.
3. **Follow the repo layout in PRD §8.8 exactly.** One concern per file. If a file grows past ~300 lines, split it by concern.
4. **Business rules live in config, not code.** Scorecard dimensions, intent buckets, objection types and failure patterns come from `config/*.yaml`. Prompts come from `backend/app/prompts/*.md`. Never hard-code them.
5. **The LLM never produces numbers we display as measurements.** Metrics (PRD §7.2) and all aggregates (§7.5) are computed in Python. The LLM writes summaries, judgements and scores against the rubric only.
6. **Every quote shown as evidence must pass `grounding.verify_quote`.** No exceptions.
7. **Vendor SDKs are imported only inside `backend/app/providers/`.** Everything else calls `get_transcriber()` and `get_analyzer()`.
8. **Every pipeline stage is idempotent and resumable.** Check for existing output before doing work. Write output, then mark the job done.
9. **User-facing errors use the codes and messages in `errors.py`** (PRD §6.2.2). Never show stack traces in the UI.
10. **Never log secrets or transcript text at INFO.** Never commit `.env`.

## Build order (one milestone at a time; stop and summarise after each)
- **M0** skeleton → **M1** uploader and ingest → **M2** pipeline and SSE progress → **M3** per-call analysis and Call Detail → **M4** Leads list and Lead Details → **M5** AI vs Human → **M6** polish.
- Each milestone's acceptance criteria are in PRD §11. Don't start the next milestone until the current one's criteria pass and its tests are green.
- Build with **fake providers first** (`FakeTranscriber`, `FakeAnalyzer` returning fixtures) so the whole flow works with no API keys. Then add the real providers.

## Commands (keep these working at all times)
```bash
make setup                  # uv sync (Python 3.12 + deps), npm install, .env from .env.example, migrate
make dev                    # API (uvicorn :8000) + worker (auto-restart) + Vite (:5173); Ctrl+C stops all
make worker                 # worker only
make test                   # pytest + vitest
make lint                   # ruff + mypy (backend), oxlint + tsc (frontend)
make migration name="..."   # after editing models.py → autogenerate an Alembic migration, then `make migrate`
make eval                   # (P1, not yet built) run labelled eval set and print agreement %
```

## Backend conventions (Python 3.12, FastAPI, SQLModel)
- Type hints everywhere. Pydantic models for every request, response and LLM contract (`schemas.py`).
- Routers in `app/api/*.py` stay thin: validate → call a function in `ingest/` or `pipeline/` → return a schema.
- Async I/O for HTTP and provider calls. CPU or subprocess work (ffmpeg) goes through `asyncio.to_thread` or `asyncio.create_subprocess_exec`.
- Database: CockroachDB in the cloud (`DATABASE_URL`), or SQLite locally (WAL + `busy_timeout=5000`, set in `db.py`). Use short transactions. The atomic job-claim SQL is in PRD §8.3.
- Files never go to the local disk: read and write them only through `app/storage.py` (stored in the database). Use `storage.local_copy()` when a tool needs a real file.
- Retries: one helper `with_retries(fn, retry_on=..., max_attempts=4)` with exponential backoff and jitter. Reuse it everywhere.
- Rate limiting: one simple async token bucket per provider in `providers/base.py`.
- Time: store UTC and display in `DEFAULT_TIMEZONE` (Asia/Kolkata). Relative dates ("kal", "tomorrow") are resolved in `grounding.py`.
- Phone numbers: normalise to E.164 with `phonenumbers`, and mask in API responses when `MASK_PHONES=true`.
- Format with ruff. Write docstrings only where the *why* isn't obvious.

## Frontend conventions (React + Vite + TS + Tailwind + shadcn/ui)
- Pages in `src/pages`, reusable pieces in `src/components`, API calls only through `src/lib/api.ts` (typed). Server data goes through TanStack Query, and there's no global store.
- Colours and spacing come **only** from `src/styles/tokens.css` variables (PRD §9.2). AI = `--ai` (blue), Human = `--human` (orange). AI is always on the left, Human on the right.
- Upload logic lives in `src/lib/upload/` as a small state machine: `idle → hashing → uploading ⇄ paused → verifying → done | failed`. The UI only renders state.
- Live progress uses `src/lib/sse.ts` (EventSource with an automatic 3 s polling fallback).
- Every list has an empty, loading (skeleton) and error state. Every chart has a table alternative.
- Accessibility: keyboard reachable, visible focus rings, `aria-live` on progress, and colour is never the only signal.
- Name components after what they show: `IntentCard`, `ObjectionCard`, `DivergingBarChart`, `EvidenceQuote`, `StagePill`.

## Testing
- Pure logic (metrics, grounding, zip reader, sheet reader, chunks) needs unit tests with hand-checked expected values.
- `test_pipeline_fake_providers.py` runs a whole batch (fixture ZIP with an AI call, a human call and a broken link) end to end without network access.
- Fixtures live in `backend/tests/fixtures/`. Don't call real APIs in tests.

## Current state
- **M0 is done** (see README "Build progress" and "Decisions"). Start the next session at **M1**.
- Record every new judgement call in README → "Decisions".

## When unsure
- If the PRD is ambiguous, pick the simplest option consistent with it, write the assumption in `README.md` under "Decisions", and mention it in your summary.
- Don't build P2 items. Build P1 only after all P0 items in a milestone are done.

## After each milestone, report
1. What was built (files touched)
2. How to run or verify it (exact commands, URL)
3. Test results (paste the real output summary)
4. Assumptions made and anything skipped
