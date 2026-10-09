"""Database engine, sessions and the UTC datetime column type.

Two setups:
- Cloud (DATABASE_URL in .env): CockroachDB (or Postgres). Paste the connection string as the provider
  shows it (postgresql://…); `engine_url()` picks the right driver. Everything — including recordings —
  is stored there (see app/storage.py), so nothing is kept on the local disk.
- Local (no DATABASE_URL): a SQLite file in DATA_DIR, in WAL mode so the API and the worker
  (two processes) can read and write at the same time.
"""

from collections.abc import Iterator
from datetime import UTC, datetime
from functools import lru_cache
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import certifi
from sqlalchemy import DateTime, event
from sqlalchemy.engine import Engine
from sqlalchemy.types import TypeDecorator
from sqlmodel import Session, create_engine

from app.config import get_settings


def utcnow() -> datetime:
    return datetime.now(UTC)


class UTCDateTime(TypeDecorator[datetime]):
    """Stores datetimes as UTC and always returns timezone-aware UTC values.

    SQLite has no timezone support, so without this, values come back "naive" and the API
    would send times without a 'Z' — which browsers would misread as local time.
    """

    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect) -> datetime | None:  # type: ignore[no-untyped-def]
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError("naive datetime given; use app.db.utcnow() or attach a timezone")
        return value.astimezone(UTC).replace(tzinfo=None)

    def process_result_value(self, value: datetime | None, dialect) -> datetime | None:  # type: ignore[no-untyped-def]
        return value.replace(tzinfo=UTC) if value is not None else None


def engine_url(url: str) -> str:
    """postgresql://… → the driver SQLAlchemy needs. CockroachDB gets its own dialect (plain Postgres
    can't read its version string). Verified TLS uses the standard CA bundle when none is given."""
    parts = urlsplit(url)
    if parts.scheme not in ("postgres", "postgresql", "cockroachdb"):
        return url  # sqlite:///… or an explicit dialect+driver
    scheme = "cockroachdb+psycopg" if "cockroach" in url else "postgresql+psycopg"
    query = dict(parse_qsl(parts.query))
    if query.get("sslmode") in ("verify-full", "verify-ca") and "sslrootcert" not in query:
        query["sslrootcert"] = certifi.where()
    return urlunsplit((scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))


@lru_cache
def get_engine() -> Engine:
    settings = get_settings()
    url = engine_url(settings.db_url)
    if url.startswith("sqlite"):
        settings.data_dir.mkdir(parents=True, exist_ok=True)
        engine = create_engine(url, connect_args={"check_same_thread": False})

        @event.listens_for(engine, "connect")
        def _sqlite_pragmas(dbapi_conn, _record):  # type: ignore[no-untyped-def]
            cur = dbapi_conn.cursor()
            cur.execute("PRAGMA journal_mode=WAL")
            cur.execute("PRAGMA busy_timeout=5000")
            cur.execute("PRAGMA foreign_keys=ON")
            cur.close()

        return engine

    connect_args: dict[str, Any] = {}
    if url.startswith("cockroachdb"):
        # Sequential ids (1, 2, 3…) instead of CockroachDB's huge random ones, which JavaScript can't
        # represent exactly — the browser would open the wrong call.
        connect_args["options"] = "-c serial_normalization=sql_sequence"
    return create_engine(
        url,
        connect_args=connect_args,
        # READ COMMITTED: the API and the worker write at the same time without "retry transaction" errors.
        isolation_level="READ COMMITTED",
        pool_pre_ping=True,  # cloud databases close idle connections
        pool_recycle=300,
    )


def get_session() -> Iterator[Session]:
    """FastAPI dependency: one short-lived session per request."""
    with Session(get_engine()) as session:
        yield session
