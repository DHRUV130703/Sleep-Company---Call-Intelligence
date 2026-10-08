"""Database tables (PRD §8.3).

Conventions:
- All times are timezone-aware UTC (`UTCDateTime`). Use `utcnow()`.
- JSON columns hold structured results (transcript segments, analysis output, stats).
- After changing a table: `make migration name="what changed"`, then `make migrate`.
"""

from datetime import date, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

from sqlalchemy import JSON, Column, Index
from sqlmodel import Field, SQLModel

from app.db import UTCDateTime, utcnow


def _created_at() -> Any:
    return Field(default_factory=utcnow, sa_type=UTCDateTime)


def _json(default: Any = None) -> Any:
    factory = (lambda: None) if default is None else (lambda: type(default)())
    return Field(default_factory=factory, sa_column=Column(JSON, nullable=default is None))


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class AgentType(StrEnum):
    ai = "ai"
    human = "human"


class AgentTypeMode(StrEnum):
    ai = "ai"
    human = "human"
    column = "column"  # read per row from the spreadsheet


class SourceType(StrEnum):
    zip = "zip"
    sheet = "sheet"
    links = "links"
    files = "files"


class TranscriptScript(StrEnum):
    roman = "roman"
    devanagari = "devanagari"
    english = "english"


class BatchStatus(StrEnum):
    processing = "processing"
    done = "done"
    cancelled = "cancelled"


class UploadStatus(StrEnum):
    receiving = "receiving"
    complete = "complete"
    failed = "failed"


class CallStage(StrEnum):
    queued = "queued"
    downloading = "downloading"
    preparing = "preparing"
    transcribing = "transcribing"
    analysing = "analysing"
    done = "done"


class CallStatus(StrEnum):
    queued = "queued"
    running = "running"
    done = "done"
    failed = "failed"
    skipped = "skipped"


class JobStatus(StrEnum):
    queued = "queued"
    running = "running"
    done = "done"
    failed = "failed"


class LeadStatus(StrEnum):
    follow_up_pending = "follow_up_pending"
    callback_scheduled = "callback_scheduled"
    store_visit_planned = "store_visit_planned"
    won = "won"
    lost = "lost"
    not_qualified = "not_qualified"


class ActionSource(StrEnum):
    ai = "ai"
    manual = "manual"


# ---------------------------------------------------------------------------
# Tables
# ---------------------------------------------------------------------------


class Batch(SQLModel, table=True):
    __tablename__ = "batches"

    id: int | None = Field(default=None, primary_key=True)
    name: str
    campaign: str = ""
    source_type: SourceType
    agent_type_mode: AgentTypeMode
    transcript_script: TranscriptScript = TranscriptScript.roman
    status: BatchStatus = BatchStatus.processing
    created_at: datetime = _created_at()
    stats: dict = _json({})  # processing time, token usage, counts


class Upload(SQLModel, table=True):
    __tablename__ = "uploads"

    id: str = Field(default_factory=lambda: uuid4().hex, primary_key=True)
    filename: str
    size: int
    sha256: str | None = None
    mime: str = ""
    chunk_size: int  # received chunks are the .part files on disk (safe with parallel uploads)
    status: UploadStatus = UploadStatus.receiving
    file_path: str | None = None
    created_at: datetime = _created_at()


class Lead(SQLModel, table=True):
    __tablename__ = "leads"
    __table_args__ = (Index("ix_leads_bucket_last_call", "intent_bucket", "last_call_at"),)

    id: int | None = Field(default=None, primary_key=True)
    phone_e164: str | None = Field(default=None, unique=True)
    name: str = ""
    owner: str = ""  # agent/store on the latest call
    assignee: str = ""  # set by a person on the Lead page
    status: LeadStatus = LeadStatus.follow_up_pending
    status_overridden: bool = False  # True once a person changes the status by hand
    intent_score: int | None = None
    intent_bucket: str | None = None
    path_summary: dict | None = _json()  # "Path to conversion" panel
    last_call_at: datetime | None = Field(default=None, sa_type=UTCDateTime)
    created_at: datetime = _created_at()
    updated_at: datetime = _created_at()


class Call(SQLModel, table=True):
    __tablename__ = "calls"
    __table_args__ = (Index("ix_calls_batch_status", "batch_id", "status"),)

    id: int | None = Field(default=None, primary_key=True)
    batch_id: int = Field(foreign_key="batches.id")
    label: str
    agent_type: AgentType
    agent_name: str = ""
    campaign: str = ""
    lead_id: int | None = Field(default=None, foreign_key="leads.id", index=True)
    external_id: str = ""
    source_url: str | None = None
    upload_id: str | None = Field(default=None, foreign_key="uploads.id")
    audio_sha256: str | None = Field(default=None, index=True)
    raw_path: str | None = None
    audio_path: str | None = None
    duration_s: float | None = None
    channels: int | None = None
    call_datetime: datetime | None = Field(default=None, sa_type=UTCDateTime)
    stage: CallStage = CallStage.queued
    status: CallStatus = CallStatus.queued
    error_code: str | None = None
    error_detail: str | None = None
    attempts: int = 0
    created_at: datetime = _created_at()
    updated_at: datetime = _created_at()


class Transcript(SQLModel, table=True):
    __tablename__ = "transcripts"

    id: int | None = Field(default=None, primary_key=True)
    call_id: int = Field(foreign_key="calls.id", index=True)
    provider: str
    model: str = ""
    language: str = ""
    script: TranscriptScript = TranscriptScript.roman
    segments: list = _json([])  # [{i, speaker: "agent"|"customer", start, end, text}]
    speaker_map: dict = _json({})  # raw diarisation label → role
    created_at: datetime = _created_at()


class Analysis(SQLModel, table=True):
    __tablename__ = "analyses"

    id: int | None = Field(default=None, primary_key=True)
    call_id: int = Field(foreign_key="calls.id", index=True)
    provider: str
    model: str = ""
    prompt_version: str = ""
    result: dict = _json({})  # validated CallAnalysis (PRD §7.1)
    quality_pct: float | None = None
    intent_score: int | None = None
    intent_bucket: str | None = None
    disposition: str | None = None
    created_at: datetime = _created_at()


class CallMetrics(SQLModel, table=True):
    __tablename__ = "metrics"

    call_id: int = Field(foreign_key="calls.id", primary_key=True)
    data: dict = _json({})  # PRD §7.2 values, computed in code


class Action(SQLModel, table=True):
    __tablename__ = "actions"

    id: int | None = Field(default=None, primary_key=True)
    lead_id: int = Field(foreign_key="leads.id", index=True)
    call_id: int | None = Field(default=None, foreign_key="calls.id")
    title: str
    say: str = ""
    why: str = ""
    due_date: date | None = None
    done: bool = False
    source: ActionSource = ActionSource.ai


class Note(SQLModel, table=True):
    __tablename__ = "notes"

    id: int | None = Field(default=None, primary_key=True)
    lead_id: int = Field(foreign_key="leads.id", index=True)
    body: str
    created_at: datetime = _created_at()


class Job(SQLModel, table=True):
    """One unit of pipeline work: run `stage` for `call_id`. Claimed atomically by the worker."""

    __tablename__ = "jobs"
    __table_args__ = (Index("ix_jobs_claim", "status", "stage", "run_after"),)

    id: int | None = Field(default=None, primary_key=True)
    call_id: int = Field(foreign_key="calls.id", index=True)
    stage: CallStage
    status: JobStatus = JobStatus.queued
    run_after: datetime = _created_at()
    attempts: int = 0
    locked_at: datetime | None = Field(default=None, sa_type=UTCDateTime)
    last_error: str | None = None


class JobEvent(SQLModel, table=True):
    """Progress feed for the live Batch page (read by the SSE endpoint)."""

    __tablename__ = "job_events"
    __table_args__ = (Index("ix_job_events_batch", "batch_id", "id"),)

    id: int | None = Field(default=None, primary_key=True)
    batch_id: int = Field(foreign_key="batches.id")
    call_id: int | None = Field(default=None, foreign_key="calls.id")
    stage: CallStage
    status: CallStatus
    message: str = ""
    progress: int = 0  # 0–100 within the stage
    created_at: datetime = _created_at()


class Comparison(SQLModel, table=True):
    __tablename__ = "comparisons"

    id: int | None = Field(default=None, primary_key=True)
    scope_hash: str = Field(index=True)
    data_version: str
    result: dict = _json({})
    created_at: datetime = _created_at()


class TranscriptCache(SQLModel, table=True):
    """Same audio bytes → reuse the transcript instead of paying for it twice."""

    __tablename__ = "transcript_cache"

    audio_sha256: str = Field(primary_key=True)
    transcript_id: int = Field(foreign_key="transcripts.id")
