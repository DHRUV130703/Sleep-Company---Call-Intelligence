"""Database engine, sessions and the UTC datetime column type.

SQLite runs in WAL mode so the API and the worker (two processes) can read and write at the same time.
Swap to Postgres by setting DATABASE_URL in .env.
"""

from collections.abc import Iterator
from datetime import UTC, datetime
from functools import lru_cache

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


@lru_cache
def get_engine() -> Engine:
    settings = get_settings()
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    url = settings.db_url
    is_sqlite = url.startswith("sqlite")
    engine = create_engine(url, connect_args={"check_same_thread": False} if is_sqlite else {})

    if is_sqlite:

        @event.listens_for(engine, "connect")
        def _sqlite_pragmas(dbapi_conn, _record):  # type: ignore[no-untyped-def]
            cur = dbapi_conn.cursor()
            cur.execute("PRAGMA journal_mode=WAL")
            cur.execute("PRAGMA busy_timeout=5000")
            cur.execute("PRAGMA foreign_keys=ON")
            cur.close()

    return engine


def get_session() -> Iterator[Session]:
    """FastAPI dependency: one short-lived session per request."""
    with Session(get_engine()) as session:
        yield session
