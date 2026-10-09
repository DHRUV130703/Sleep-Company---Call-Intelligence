"""Tables that replace the local disk: files (recordings, uploads, spreadsheets) and the worker heartbeat.

Files are stored in the database so the app keeps no data on the machine it runs on. See app/storage.py.
"""

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, BigInteger, Column, LargeBinary
from sqlmodel import Field, SQLModel

from app.db import UTCDateTime, utcnow


def _created_at() -> Any:
    return Field(default_factory=utcnow, sa_type=UTCDateTime)


class Blob(SQLModel, table=True):
    """One stored file. Its bytes are in `blob_parts`. The row is written last, so it only exists once
    every part is saved — a half-written file is never visible."""

    __tablename__ = "blobs"

    key: str = Field(primary_key=True)  # e.g. "audio/norm/<sha256>.mp3"
    size: int = Field(sa_type=BigInteger)  # bytes (files can exceed 2 GB)
    parts: int
    content_type: str = "application/octet-stream"
    created_at: datetime = _created_at()


class BlobPart(SQLModel, table=True):
    """Up to 1 MB of one file's bytes (CockroachDB works best with values of a few MB at most)."""

    __tablename__ = "blob_parts"

    key: str = Field(primary_key=True)
    idx: int = Field(primary_key=True)
    data: bytes = Field(sa_column=Column(LargeBinary, nullable=False))


class WorkerHeartbeat(SQLModel, table=True):
    """The worker writes the time here every few seconds; Settings → Health shows whether it is alive."""

    __tablename__ = "worker_heartbeats"

    name: str = Field(primary_key=True)  # "worker"
    beat_at: datetime = _created_at()


class SavedReport(SQLModel, table=True):
    """A generated report file (PDF, Word, Excel, CSV, JSON), kept so it can be downloaded again or shared.

    The file itself is in storage under `storage_key`; `url` is its public download link
    (GET /api/reports/<token>/<filename> — anyone with the link can open it, like a shared Google Doc link)."""

    __tablename__ = "reports"

    id: int | None = Field(default=None, primary_key=True)
    token: str = Field(index=True, unique=True)  # random; makes the public link unguessable
    kind: str = "ai_vs_human"
    format: str  # pdf | docx | xlsx | csv | json
    filename: str
    content_type: str
    size: int = Field(sa_type=BigInteger)
    storage_key: str
    url: str
    scope: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))  # which calls it covers
    scope_hash: str = Field(index=True)
    report_built_at: str  # generated_at of the comparison it was made from
    created_at: datetime = _created_at()
