# LimeZip Call Intelligence — every command you need.
#   make setup      first-time install (Python deps, Node deps, .env, database)
#   make dev        run everything: API :8000, worker, web app :5173  (Ctrl+C stops all)
#   make test       backend + frontend tests
#   make lint       code checks (ruff, mypy, oxlint, tsc)
#   make move-to-cloud   one time: copy local data/ into the cloud database in DATABASE_URL

SHELL := /bin/bash
BACKEND := backend
VENV := $(BACKEND)/.venv/bin

.PHONY: setup migrate migration move-to-cloud dev api worker web test lint format

setup:
	@command -v uv >/dev/null || { echo "✗ uv is required: https://docs.astral.sh/uv/  (macOS: brew install uv)"; exit 1; }
	@command -v node >/dev/null || { echo "✗ Node.js 20+ is required: https://nodejs.org"; exit 1; }
	@command -v ffmpeg >/dev/null || echo "⚠ ffmpeg not found — install it before processing calls (macOS: brew install ffmpeg)"
	cd $(BACKEND) && uv sync --extra dev
	cd frontend && npm install
	@test -f .env || { cp .env.example .env; echo "✓ Created .env — add your API keys there"; }
	@$(MAKE) --no-print-directory migrate
	@echo "✓ Setup complete. Run: make dev"

migrate:
	cd $(BACKEND) && .venv/bin/alembic upgrade head

# One time, after setting DATABASE_URL in .env: copy the local database and files to the cloud database.
move-to-cloud: migrate
	cd $(BACKEND) && .venv/bin/python -m app.move_to_cloud

# After changing backend/app/models.py:  make migration name="add notes pinned flag"
migration:
	@test -n "$(name)" || { echo 'Usage: make migration name="what changed"'; exit 1; }
	cd $(BACKEND) && .venv/bin/alembic revision --autogenerate -m "$(name)"

dev: migrate
	@echo ""
	@echo "  App  → http://localhost:5173"
	@echo "  API  → http://127.0.0.1:8000/docs"
	@echo ""
	@trap 'kill 0' INT TERM EXIT; \
	  $(MAKE) --no-print-directory api & \
	  $(MAKE) --no-print-directory worker-dev & \
	  $(MAKE) --no-print-directory web & \
	  wait

api:
	cd $(BACKEND) && .venv/bin/uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

worker:
	cd $(BACKEND) && .venv/bin/python -m app.worker

# Same as `worker`, but restarts automatically when backend code changes.
worker-dev:
	cd $(BACKEND) && .venv/bin/watchfiles --filter python ".venv/bin/python -m app.worker" app

web:
	cd frontend && npm run dev

test:
	cd $(BACKEND) && .venv/bin/pytest -q
	cd frontend && npm test

lint:
	cd $(BACKEND) && .venv/bin/ruff check . && .venv/bin/ruff format --check . && .venv/bin/mypy app
	cd frontend && npm run lint && npm run typecheck

format:
	cd $(BACKEND) && .venv/bin/ruff format . && .venv/bin/ruff check --fix .
