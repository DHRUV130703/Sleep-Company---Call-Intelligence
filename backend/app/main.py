"""FastAPI app. Run with `make dev` (or `uvicorn app.main:app --reload` from backend/)."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api import batches, calls, compare, leads, uploads
from app.api import settings as settings_api
from app.config import get_settings
from app.errors import install_error_handlers
from app.log import setup_logging


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    setup_logging()
    get_settings().data_dir.mkdir(parents=True, exist_ok=True)
    yield


app = FastAPI(title="LimeZip Call Intelligence", version=__version__, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[get_settings().frontend_origin, "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)
install_error_handlers(app)

for router in (
    settings_api.router,
    uploads.router,
    batches.router,
    calls.router,
    leads.router,
    compare.router,
):
    app.include_router(router, prefix="/api")
