"""Batches: create, list, live progress (Server-Sent Events), retry, cancel (PRD §6.2)."""

import asyncio
import json
from collections.abc import AsyncIterator
from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy import select as sa_select  # sqlmodel select() is typed for at most 4 columns
from sqlmodel import Session, col, select

from app.api.views import call_row, iso
from app.db import get_engine, get_session, utcnow
from app.errors import AppError, ErrorCode
from app.ingest.batches import BatchInput, create_batch
from app.models import (
    AgentTypeMode,
    Analysis,
    Batch,
    BatchStatus,
    Call,
    CallStage,
    CallStatus,
    Job,
    JobEvent,
    JobStatus,
    TranscriptScript,
)

router = APIRouter(tags=["batches"])


class BatchCreate(BaseModel):
    name: str = ""
    campaign: str = ""
    agent_type_mode: AgentTypeMode
    transcript_script: TranscriptScript = TranscriptScript.roman
    files: list[dict[str, Any]] = []
    sheet: dict[str, Any] | None = None
    links: list[dict[str, Any]] = []


def _counts(session: Session, batch_ids: list[int]) -> dict[int, dict[str, Any]]:
    rows = session.execute(
        sa_select(
            col(Call.batch_id),
            col(Call.agent_type),
            col(Call.status),
            func.count(),
            func.sum(Call.duration_s),
        )
        .where(col(Call.batch_id).in_(batch_ids))
        .group_by(col(Call.batch_id), col(Call.agent_type), col(Call.status))
    ).all()
    out: dict[int, dict[str, Any]] = {
        b: {"total": 0, "ai": 0, "human": 0, "audio_seconds": 0.0, **{s.value: 0 for s in CallStatus}}
        for b in batch_ids
    }
    for batch_id, agent_type, status, n, secs in rows:
        c = out[batch_id]
        c["total"] += n
        c[agent_type] += n
        c[status] += n
        c["audio_seconds"] += float(secs or 0)
    return out


def _batch_json(batch: Batch, counts: dict[str, Any]) -> dict[str, Any]:
    finished = counts["done"] + counts["failed"] + counts["skipped"]
    remaining = counts["queued"] + counts["running"]
    eta = None
    if remaining and finished and batch.status == BatchStatus.processing:
        elapsed = (utcnow() - batch.created_at).total_seconds()
        eta = round(elapsed / finished * remaining)
    return {
        "id": batch.id,
        "name": batch.name,
        "campaign": batch.campaign,
        "source_type": batch.source_type,
        "agent_type_mode": batch.agent_type_mode,
        "transcript_script": batch.transcript_script,
        "status": batch.status,
        "created_at": iso(batch.created_at),
        "finished_at": (batch.stats or {}).get("finished_at"),
        "counts": counts,
        "eta_seconds": eta,
        "skipped_inputs": (batch.stats or {}).get("skipped_inputs", []),
    }


@router.post("/batches")
def create(body: BatchCreate, session: Session = Depends(get_session)) -> dict:
    batch = create_batch(session, BatchInput(**body.model_dump()))
    assert batch.id is not None
    return _batch_json(batch, _counts(session, [batch.id])[batch.id])


@router.get("/batches")
def list_batches(session: Session = Depends(get_session)) -> dict:
    batches = session.exec(select(Batch).order_by(col(Batch.id).desc())).all()
    counts = _counts(session, [b.id for b in batches if b.id is not None])
    return {"items": [_batch_json(b, counts[b.id]) for b in batches if b.id is not None]}


def _get_batch(session: Session, batch_id: int) -> Batch:
    batch = session.get(Batch, batch_id)
    if batch is None:
        raise AppError(ErrorCode.NOT_FOUND, "Batch not found.")
    return batch


@router.get("/batches/{batch_id}")
def batch_detail(batch_id: int, session: Session = Depends(get_session)) -> dict:
    batch = _get_batch(session, batch_id)
    calls = session.exec(select(Call).where(Call.batch_id == batch_id).order_by(col(Call.id))).all()
    analyses = {
        a.call_id: a
        for a in session.exec(select(Analysis).where(col(Analysis.call_id).in_([c.id for c in calls])))
    }
    last_event = session.exec(select(func.max(JobEvent.id)).where(JobEvent.batch_id == batch_id)).one()
    latest_ids = (
        select(func.max(JobEvent.id)).where(JobEvent.batch_id == batch_id).group_by(col(JobEvent.call_id))
    )
    messages = {
        e.call_id: e.message for e in session.exec(select(JobEvent).where(col(JobEvent.id).in_(latest_ids)))
    }
    return {
        **_batch_json(batch, _counts(session, [batch_id])[batch_id]),
        "calls": [
            {**call_row(c, analyses.get(c.id)), "message": messages.get(c.id, "")}  # type: ignore[arg-type]
            for c in calls
        ],
        "last_event_id": last_event or 0,
    }


@router.get("/batches/{batch_id}/events")
async def batch_events(batch_id: int, request: Request, after: int = 0) -> StreamingResponse:
    """Live progress. Each message: {"call_id", "stage", "status", "message", "progress", "event_id"}."""

    async def stream() -> AsyncIterator[str]:
        last_id, idle = after, 0
        yield "retry: 3000\n\n"
        while not await request.is_disconnected():
            with Session(get_engine()) as s:
                events = s.exec(
                    select(JobEvent)
                    .where(JobEvent.batch_id == batch_id, col(JobEvent.id) > last_id)
                    .order_by(col(JobEvent.id))
                    .limit(500)
                ).all()
                batch = s.get(Batch, batch_id)
                status = batch.status if batch else BatchStatus.done
            for e in events:
                last_id = e.id or last_id
                payload = {
                    "event_id": e.id,
                    "call_id": e.call_id,
                    "stage": e.stage,
                    "status": e.status,
                    "message": e.message,
                    "progress": e.progress,
                }
                yield f"id: {e.id}\ndata: {json.dumps(payload)}\n\n"
            if events:
                idle = 0
            else:
                idle += 1
                if status != BatchStatus.processing:
                    yield f"event: finished\ndata: {json.dumps({'status': status})}\n\n"
                    return
                if idle % 15 == 0:
                    yield ": keep-alive\n\n"
            await asyncio.sleep(1)

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def requeue_call(session: Session, call: Call, stage: CallStage | None = None) -> None:
    """Put a call back in the queue at `stage` (default: the stage where it stopped)."""
    assert call.id is not None
    start = stage or (call.stage if call.stage != CallStage.done else CallStage.analysing)
    if start == CallStage.queued:
        start = CallStage.downloading if call.source_url and not call.raw_path else CallStage.preparing
    for j in session.exec(select(Job).where(Job.call_id == call.id, Job.status == JobStatus.queued)).all():
        session.delete(j)
    session.add(Job(call_id=call.id, stage=start))
    call.status, call.stage, call.error_code, call.error_detail = CallStatus.queued, start, None, None
    call.updated_at = utcnow()
    session.add(call)
    session.add(
        JobEvent(
            batch_id=call.batch_id,
            call_id=call.id,
            stage=start,
            status=CallStatus.queued,
            message="Waiting (retry)",
        )
    )
    batch = session.get(Batch, call.batch_id)
    if batch and batch.status != BatchStatus.processing:
        batch.status = BatchStatus.processing
        session.add(batch)


@router.post("/batches/{batch_id}/retry-failed")
def retry_failed(batch_id: int, session: Session = Depends(get_session)) -> dict:
    _get_batch(session, batch_id)
    calls = session.exec(
        select(Call).where(Call.batch_id == batch_id, Call.status == CallStatus.failed)
    ).all()
    for c in calls:
        requeue_call(session, c)
    session.commit()
    return {"retried": len(calls)}


@router.post("/batches/{batch_id}/cancel")
def cancel(batch_id: int, session: Session = Depends(get_session)) -> dict:
    batch = _get_batch(session, batch_id)
    calls = session.exec(
        select(Call).where(Call.batch_id == batch_id, Call.status == CallStatus.queued)
    ).all()
    for c in calls:
        for j in session.exec(select(Job).where(Job.call_id == c.id, Job.status == JobStatus.queued)).all():
            j.status = JobStatus.failed
            j.last_error = "Cancelled"
            session.add(j)
        c.status, c.error_code, c.error_detail = CallStatus.skipped, ErrorCode.CANCELLED.value, None
        session.add(c)
        session.add(
            JobEvent(
                batch_id=batch_id, call_id=c.id, stage=c.stage, status=CallStatus.skipped, message="Cancelled"
            )
        )
    running = session.exec(
        select(Call.id).where(Call.batch_id == batch_id, Call.status == CallStatus.running)
    ).first()
    if running is None:
        batch.status = BatchStatus.cancelled
        session.add(batch)
    session.commit()
    return {"cancelled": len(calls)}
