"""Vercel entry point: the FastAPI app (backend/app) runs as one Python function.

vercel.json sends every /api/* request here; the web app (frontend/dist) is served as static files.
The background worker does NOT run on Vercel — run `make worker` on a machine that stays on.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from app.main import app  # noqa: E402

__all__ = ["app"]
