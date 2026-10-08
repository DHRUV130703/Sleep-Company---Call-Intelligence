"""Calls: list, detail (transcript + analysis + metrics), audio, retry, re-analyse, swap speakers."""

from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, Query
from fastapi.responses import FileResponse
from sqlalchemy import func, or_
from sqlmodel import Session, col, select

from app.api.batches import requeue_call
from app.api.views import call_row, lead_row
from app.db import get_session
from app.errors import AppError, ErrorCode
from app.models import AgentType, Analysis, Call, CallMetrics, CallStage, CallStatus, Lead, Transcript
from app.pipeline.metrics import METRIC_LABELS, compute_metrics
from app.pipeline.transliterate import has_devanagari, to_roman

router = APIRouter(tags=["calls"])


def _get_call(session: Session, call_id: int) -> Call:
    call = session.get(Call, call_id)
    if call is None:
        raise AppError(ErrorCode.NOT_FOUND, "Call not found.")
    return call


@router.get("/calls")
def list_calls(
    batch_id: int | None = None,
    lead_id: int | None = None,
    agent_type: AgentType | None = None,
    status: CallStatus | None = None,
    q: str = "",
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    session: Session = Depends(get_session),
) -> dict:
    filters: list[Any] = []
    if batch_id:
        filters.append(Call.batch_id == batch_id)
    if lead_id:
        filters.append(Call.lead_id == lead_id)
    if agent_type:
        filters.append(Call.agent_type == agent_type)
    if status:
        filters.append(Call.status == status)
    if q.strip():
        like = f"%{q.strip()}%"
        filters.append(
            or_(col(Call.label).ilike(like), col(Call.agent_name).ilike(like), col(Call.campaign).ilike(like))
        )
    total = session.exec(select(func.count()).select_from(Call).where(*filters)).one()
    calls = session.exec(
        select(Call)
        .where(*filters)
        .order_by(col(Call.id).desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    ids = [c.id for c in calls]
    analyses = {a.call_id: a for a in session.exec(select(Analysis).where(col(Analysis.call_id).in_(ids)))}
    leads = {
        ld.id: ld for ld in session.exec(select(Lead).where(col(Lead.id).in_([c.lead_id for c in calls])))
    }
    return {
        "items": [call_row(c, analyses.get(c.id), leads.get(c.lead_id)) for c in calls],  # type: ignore[arg-type]
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/calls/{call_id}")
def call_detail(call_id: int, session: Session = Depends(get_session)) -> dict:
    call = _get_call(session, call_id)
    analysis = session.exec(
        select(Analysis).where(Analysis.call_id == call_id).order_by(col(Analysis.id).desc())
    ).first()
    transcript = session.exec(
        select(Transcript).where(Transcript.call_id == call_id).order_by(col(Transcript.id).desc())
    ).first()
    metrics = session.get(CallMetrics, call_id)
    lead = session.get(Lead, call.lead_id) if call.lead_id else None
    return {
        **call_row(call, analysis, lead),
        "lead": lead_row(lead) if lead else None,
        "has_audio": bool(call.audio_path and Path(call.audio_path).exists()),
        "transcript": {
            "provider": transcript.provider,
            "model": transcript.model,
            "script": transcript.script,
            # Each line as spoken (original script) plus the same words in English letters (no translation).
            "segments": [{**seg, "text_roman": to_roman(seg["text"])} for seg in transcript.segments],
            "has_other_script": any(has_devanagari(seg["text"]) for seg in transcript.segments),
        }
        if transcript
        else None,
        "analysis": {
            **analysis.result,
            "prompt_version": analysis.prompt_version,
            "model": analysis.model,
            "created_at": analysis.created_at.isoformat(),
        }
        if analysis
        else None,
        "metrics": metrics.data if metrics else None,
        "metric_labels": METRIC_LABELS,
    }


@router.get("/calls/{call_id}/audio")
def call_audio(call_id: int, session: Session = Depends(get_session)) -> FileResponse:
    """Normalised audio. FileResponse supports HTTP Range, so the player can seek."""
    call = _get_call(session, call_id)
    if not call.audio_path or not Path(call.audio_path).exists():
        raise AppError(ErrorCode.NOT_FOUND, "Audio isn't available for this call.")
    return FileResponse(
        call.audio_path,
        media_type="audio/mpeg",
        filename=f"call-{call_id}.mp3",
        content_disposition_type="inline",
    )


@router.post("/calls/{call_id}/retry")
def retry_call(call_id: int, session: Session = Depends(get_session)) -> dict:
    call = _get_call(session, call_id)
    if call.status in (CallStatus.queued, CallStatus.running):
        return {"ok": True}
    requeue_call(session, call)
    session.commit()
    return {"ok": True}


@router.post("/calls/{call_id}/reanalyze")
def reanalyze_call(call_id: int, session: Session = Depends(get_session)) -> dict:
    call = _get_call(session, call_id)
    if not session.exec(select(Transcript.id).where(Transcript.call_id == call_id)).first():
        raise AppError(ErrorCode.VALIDATION_ERROR, "This call has no transcript yet.")
    requeue_call(session, call, CallStage.analysing)
    session.commit()
    return {"ok": True}


@router.post("/calls/{call_id}/swap-speakers")
def swap_speakers(call_id: int, session: Session = Depends(get_session)) -> dict:
    """Agent ↔ customer were mixed up: flip every segment, recompute metrics, re-run the analysis."""
    call = _get_call(session, call_id)
    transcript = session.exec(
        select(Transcript).where(Transcript.call_id == call_id).order_by(col(Transcript.id).desc())
    ).first()
    if transcript is None:
        raise AppError(ErrorCode.VALIDATION_ERROR, "This call has no transcript yet.")
    flip = {"agent": "customer", "customer": "agent"}
    transcript.segments = [
        {**s, "role": flip.get(s.get("role", ""), s.get("role"))} for s in transcript.segments
    ]
    transcript.speaker_map = {k: flip.get(v, v) for k, v in (transcript.speaker_map or {}).items()}
    session.add(transcript)
    metrics = session.get(CallMetrics, call_id) or CallMetrics(call_id=call_id)
    metrics.data = compute_metrics(transcript.segments, call.duration_s or 0)
    session.add(metrics)
    requeue_call(session, call, CallStage.analysing)
    session.commit()
    return {"ok": True}
