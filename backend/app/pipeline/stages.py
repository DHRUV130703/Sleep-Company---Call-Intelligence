"""The four pipeline stages (PRD §6.2.1) and the runner that executes one job.

    downloading → preparing → transcribing → analysing → done

Each stage handler receives the call id, does its work, and returns the next stage (or None when the
call is finished). Handlers are idempotent: if their output already exists they skip the work, so a
crashed or restarted worker simply carries on.
"""

import hashlib
import json
import logging
import shutil
import tempfile
import time
from collections.abc import Awaitable, Callable
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from sqlmodel import Session, col, select

from app.config import get_settings
from app.db import get_engine, utcnow
from app.errors import ErrorCode
from app.ingest import dialer_filename
from app.ingest.downloader import download
from app.models import (
    Action,
    ActionSource,
    Analysis,
    Batch,
    BatchStatus,
    Call,
    CallMetrics,
    CallStage,
    CallStatus,
    Job,
    JobStatus,
    Transcript,
    TranscriptCache,
    TranscriptScript,
)
from app.pipeline import audio
from app.pipeline.analysis import analyse_transcript, assign_speakers, provider_stage_error
from app.pipeline.errors import StageError
from app.pipeline.events import emit
from app.pipeline.leads import refresh_lead
from app.pipeline.metrics import compute_metrics
from app.providers import get_transcriber
from app.providers.base import ProviderError

log = logging.getLogger("pipeline")

MIN_DURATION_S = 5
SILENT_BELOW_DB = -50
MAX_JOB_ATTEMPTS = 4
CHUNK_OVERLAP_S = 5

StageHandler = Callable[[int], Awaitable[CallStage | None]]


def _paths() -> tuple[Path, Path]:
    d = get_settings().data_dir / "audio"
    return d / "raw", d / "norm"


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while block := f.read(1024 * 1024):
            h.update(block)
    return h.hexdigest()


def _load(session: Session, call_id: int) -> Call:
    call = session.get(Call, call_id)
    if call is None:
        raise StageError(ErrorCode.NOT_FOUND)
    return call


# ---------------------------------------------------------------------------
# Stage 1: download (links only)
# ---------------------------------------------------------------------------


async def stage_download(call_id: int) -> CallStage | None:
    raw_dir, _ = _paths()
    with Session(get_engine()) as s:
        call = _load(s, call_id)
        if call.raw_path and Path(call.raw_path).exists():
            return CallStage.preparing
        url = call.source_url
        emit(s, call, stage=CallStage.downloading, status=CallStatus.running, message="Downloading recording")
    if not url:
        raise StageError(ErrorCode.NOTHING_TO_PROCESS, detail="No file or link for this call")
    got = await download(url, raw_dir)
    with Session(get_engine()) as s:
        call = _load(s, call_id)
        call.raw_path, call.audio_sha256 = str(got.path), got.sha256
        # Dialer file names often carry the agent, campaign and call time — fill in what's missing.
        meta = dialer_filename.parse(got.filename, get_settings().default_timezone) if got.filename else {}
        call.agent_name = call.agent_name or str(meta.get("agent_name", ""))
        call.campaign = call.campaign or str(meta.get("campaign", ""))
        if call.call_datetime is None and isinstance(meta.get("call_datetime"), datetime):
            call.call_datetime = meta["call_datetime"]  # type: ignore[assignment]
        if got.filename and (call.label in ("", "command") or call.label.startswith("http")):
            call.label = Path(got.filename).stem[:120]
        s.add(call)
        s.commit()
    return CallStage.preparing


# ---------------------------------------------------------------------------
# Stage 2: prepare audio (probe, checks, normalise)
# ---------------------------------------------------------------------------


async def stage_prepare(call_id: int) -> CallStage | None:
    _, norm_dir = _paths()
    settings = get_settings()
    with Session(get_engine()) as s:
        call = _load(s, call_id)
        emit(s, call, stage=CallStage.preparing, status=CallStatus.running, message="Checking the audio")
        raw = Path(call.raw_path or "")
        sha = call.audio_sha256
    if not raw.exists():
        raise StageError(ErrorCode.NOTHING_TO_PROCESS, detail="Recording file is missing")

    try:
        info = await audio.probe(raw)
    except audio.AudioError as exc:
        raise StageError(ErrorCode.NOT_AUDIO, detail=str(exc)[:120]) from exc
    if not info.has_audio:
        raise StageError(ErrorCode.NOT_AUDIO)
    if info.duration_s > settings.max_recording_hours * 3600:
        raise StageError(ErrorCode.TOO_LONG)

    with Session(get_engine()) as s:
        call = _load(s, call_id)
        call.duration_s, call.channels = round(info.duration_s, 2), info.channels
        s.add(call)
        s.commit()
    if info.duration_s < MIN_DURATION_S:
        raise StageError(ErrorCode.TOO_SHORT, skip=True)

    sha = sha or _sha256(raw)
    norm = norm_dir / f"{sha}.mp3"
    if not norm.exists():
        try:
            await audio.normalise(raw, norm)
        except audio.AudioError as exc:
            raise StageError(ErrorCode.NOT_AUDIO, detail=str(exc)[:120]) from exc
    if await audio.max_volume_db(norm) < SILENT_BELOW_DB:
        raise StageError(ErrorCode.SILENT, skip=True)

    with Session(get_engine()) as s:
        call = _load(s, call_id)
        call.audio_sha256, call.audio_path = sha, str(norm)
        s.add(call)
        s.commit()
    return CallStage.transcribing


# ---------------------------------------------------------------------------
# Stage 3: transcribe (+ speaker roles), with cache and chunking
# ---------------------------------------------------------------------------


async def stage_transcribe(call_id: int) -> CallStage | None:
    settings = get_settings()
    with Session(get_engine()) as s:
        call = _load(s, call_id)
        if s.exec(select(Transcript).where(Transcript.call_id == call_id)).first():
            return CallStage.analysing
        emit(s, call, stage=CallStage.transcribing, status=CallStatus.running, message="Transcribing")
        sha, norm, duration = call.audio_sha256, Path(call.audio_path or ""), call.duration_s or 0
        batch = s.get(Batch, call.batch_id)
        script = batch.transcript_script if batch else TranscriptScript(settings.default_transcript_script)

        # Reuse an earlier transcript of the same audio — but only one made by the transcriber selected now
        # (switching e.g. from Whisper to AssemblyAI must produce a new transcript).
        cached = s.get(TranscriptCache, sha) if sha else None
        src = s.get(Transcript, cached.transcript_id) if cached else None
        if src and src.script == script and src.provider == get_transcriber().name:
            s.add(
                Transcript(
                    call_id=call_id,
                    provider=src.provider,
                    model=src.model,
                    language=src.language,
                    script=src.script,
                    segments=src.segments,
                    speaker_map=src.speaker_map,
                )
            )
            emit(
                s,
                call,
                stage=CallStage.transcribing,
                status=CallStatus.running,
                message="Reused previous transcript",
                progress=100,
            )
            return CallStage.analysing

    transcriber = get_transcriber()
    # Speech-to-text output is saved before the speaker step, so a retry (e.g. after logging in to
    # Claude) doesn't redo the slow transcription.
    raw_file = settings.data_dir / "transcripts_raw" / f"{sha or call_id}-{transcriber.name}.json"
    if raw_file.exists():
        raw_segments = json.loads(raw_file.read_text())
    else:
        try:
            raw_segments = await _transcribe_in_chunks(
                norm, duration, str(script), settings.chunk_minutes * 60, call_id
            )
        except ProviderError as exc:
            raise provider_stage_error(exc) from exc
        raw_file.parent.mkdir(parents=True, exist_ok=True)
        raw_file.write_text(json.dumps(raw_segments, ensure_ascii=False))
    if not raw_segments:
        raise StageError(ErrorCode.SILENT, skip=True)

    labelled = await assign_speakers(raw_segments, str(script))
    segments = [{**seg, "i": i} for i, seg in enumerate(labelled)]
    roles = {seg["speaker"]: seg["role"] for seg in segments}
    used = transcriber.last_used
    with Session(get_engine()) as s:
        t = Transcript(
            call_id=call_id,
            provider=used.name if used else "?",
            model=used.model if used else "",
            script=script,
            segments=segments,
            speaker_map=roles,
        )
        s.add(t)
        s.commit()
        s.refresh(t)
        if sha:
            cache = s.get(TranscriptCache, sha) or TranscriptCache(audio_sha256=sha, transcript_id=t.id or 0)
            cache.transcript_id = t.id or 0
            s.add(cache)
            s.commit()
    return CallStage.analysing


async def _transcribe_in_chunks(
    norm: Path, duration: float, script: str, chunk_s: int, call_id: int
) -> list[dict[str, Any]]:
    """Short calls go in one request. Long calls are cut into chunk_s pieces (+5 s overlap) and stitched."""
    transcriber = get_transcriber()
    if duration <= chunk_s + CHUNK_OVERLAP_S:
        result = await transcriber.transcribe(norm, script=script)
        return [seg.model_dump() for seg in result.segments if seg.text.strip()]

    out: list[dict[str, Any]] = []
    n_chunks = int(duration // chunk_s) + (1 if duration % chunk_s else 0)
    with tempfile.TemporaryDirectory() as tmp:
        for i in range(n_chunks):
            start = i * chunk_s
            piece = Path(tmp) / f"chunk{i}.mp3"
            await audio.cut(norm, piece, start, chunk_s + CHUNK_OVERLAP_S)
            context = "\n".join(f"{x['speaker']}: {x['text']}" for x in out[-3:])
            result = await transcriber.transcribe(piece, script=script, context=context)
            for seg in result.segments:
                # Keep a segment only if it starts inside this chunk's own window (the overlap belongs to the next).
                if seg.text.strip() and (seg.start < chunk_s or i == n_chunks - 1):
                    out.append(
                        {
                            "speaker": seg.speaker,
                            "start": round(seg.start + start, 2),
                            "end": round(seg.end + start, 2),
                            "text": seg.text.strip(),
                        }
                    )
            with Session(get_engine()) as s:
                emit(
                    s,
                    _load(s, call_id),
                    stage=CallStage.transcribing,
                    status=CallStatus.running,
                    message=f"Transcribing part {i + 1} of {n_chunks}",
                    progress=int(100 * (i + 1) / n_chunks),
                )
    return out


# ---------------------------------------------------------------------------
# Stage 4: analyse (metrics + AI analysis + lead roll-up)
# ---------------------------------------------------------------------------


async def stage_analyse(call_id: int) -> CallStage | None:
    with Session(get_engine()) as s:
        call = _load(s, call_id)
        emit(
            s,
            call,
            stage=CallStage.analysing,
            status=CallStatus.running,
            message="Analysing the conversation",
        )
        transcript = s.exec(
            select(Transcript).where(Transcript.call_id == call_id).order_by(col(Transcript.id).desc())
        ).first()
        if transcript is None:
            raise StageError(ErrorCode.ANALYSIS_INVALID, detail="No transcript")
        segments, duration = transcript.segments, call.duration_s or 0
        agent_type, campaign, call_dt = call.agent_type, call.campaign, call.call_datetime or call.created_at

        metrics = compute_metrics(segments, duration)
        existing = s.get(CallMetrics, call_id)
        if existing:
            existing.data = metrics
            s.add(existing)
        else:
            s.add(CallMetrics(call_id=call_id, data=metrics))
        s.commit()
    if metrics["customer_turns"] == 0 or metrics["agent_turns"] == 0:
        raise StageError(ErrorCode.NOT_CONNECTED, skip=True)

    result, version = await analyse_transcript(
        segments, agent_type=agent_type, campaign=campaign, call_datetime=call_dt, duration_s=duration
    )

    settings = get_settings()
    with Session(get_engine()) as s:
        call = _load(s, call_id)
        for old in s.exec(select(Analysis).where(Analysis.call_id == call_id)).all():
            s.delete(old)
        s.add(
            Analysis(
                call_id=call_id,
                provider=settings.analyzer,
                model=settings.analysis_model,
                prompt_version=version,
                result=result,
                quality_pct=result["quality_pct"],
                intent_score=result["intent"]["score"],
                intent_bucket=result["intent"]["bucket"],
                disposition=result["outcome"]["disposition"],
            )
        )
        # Replace this call's open AI actions with the new ones.
        for a in s.exec(
            select(Action).where(Action.call_id == call_id, Action.source == ActionSource.ai)
        ).all():
            if not a.done:
                s.delete(a)
        if call.lead_id:
            for na in result["next_actions"]:
                s.add(
                    Action(
                        lead_id=call.lead_id,
                        call_id=call_id,
                        title=na["title"],
                        say=na["say"],
                        why=na["why"],
                        due_date=date.fromisoformat(na["due"]) if na.get("due") else None,
                    )
                )
        s.commit()
        if call.lead_id:
            await refresh_lead(s, call.lead_id)
    return None


STAGE_HANDLERS: dict[CallStage, StageHandler] = {
    CallStage.downloading: stage_download,
    CallStage.preparing: stage_prepare,
    CallStage.transcribing: stage_transcribe,
    CallStage.analysing: stage_analyse,
}


# ---------------------------------------------------------------------------
# Runner: one job → handler → next job / retry / skip / fail
# ---------------------------------------------------------------------------


async def process_job(job: Job) -> None:
    """Run one claimed job. Never raises: every outcome is written to the database."""
    assert job.id is not None
    started = time.monotonic()
    with Session(get_engine()) as s:
        call = s.get(Call, job.call_id)
        batch = s.get(Batch, call.batch_id) if call else None
        if call is None or (batch and batch.status == BatchStatus.cancelled):
            _finish(s, job.id, JobStatus.done)
            return

    try:
        next_stage = await STAGE_HANDLERS[job.stage](job.call_id)
    except StageError as exc:
        await _handle_stage_error(job, exc)
        return
    except Exception as exc:
        log.exception("stage crashed", extra={"call_id": job.call_id, "stage": job.stage})
        await _handle_stage_error(
            job, StageError(ErrorCode.INTERNAL_ERROR, detail=f"{type(exc).__name__}: {exc}"[:200])
        )
        return

    with Session(get_engine()) as s:
        call = _load(s, job.call_id)
        _finish(s, job.id, JobStatus.done, commit=False)
        if next_stage is None:
            call.error_code = call.error_detail = None
            emit(
                s,
                call,
                stage=CallStage.done,
                status=CallStatus.done,
                message="Done",
                progress=100,
                commit=False,
            )
        else:
            s.add(Job(call_id=job.call_id, stage=next_stage))
            emit(s, call, stage=next_stage, status=CallStatus.queued, message="Waiting", commit=False)
        s.commit()
        _update_batch(s, call.batch_id, time.monotonic() - started)
    log.info(
        "stage done",
        extra={
            "call_id": job.call_id,
            "stage": job.stage,
            "duration_ms": int((time.monotonic() - started) * 1000),
        },
    )


async def _handle_stage_error(job: Job, exc: StageError) -> None:
    assert job.id is not None
    with Session(get_engine()) as s:
        call = _load(s, job.call_id)
        if exc.retryable and job.attempts < MAX_JOB_ATTEMPTS:
            j = s.get(Job, job.id)
            assert j is not None
            j.status, j.locked_at, j.last_error = JobStatus.queued, None, exc.message
            j.run_after = utcnow() + timedelta(seconds=30 * job.attempts)
            s.add(j)
            emit(
                s,
                call,
                stage=job.stage,
                status=CallStatus.queued,
                message=f"{exc.message} Retrying (attempt {job.attempts + 1} of {MAX_JOB_ATTEMPTS}).",
            )
            return
        _finish(s, job.id, JobStatus.failed, error=exc.message, commit=False)
        call.error_code, call.error_detail = exc.code.value, exc.message
        call.attempts += 1
        emit(
            s,
            call,
            stage=job.stage,
            status=CallStatus.skipped if exc.skip else CallStatus.failed,
            message=exc.message,
            commit=False,
        )
        s.commit()
        if exc.skip and call.lead_id:
            await refresh_lead(s, call.lead_id)  # lead becomes "Not available" if nothing connected
        _update_batch(s, call.batch_id, 0)


def _finish(
    s: Session, job_id: int, status: JobStatus, error: str | None = None, commit: bool = True
) -> None:
    j = s.get(Job, job_id)
    if j:
        j.status, j.locked_at, j.last_error = status, None, error
        s.add(j)
        if commit:
            s.commit()


def _update_batch(s: Session, batch_id: int, stage_seconds: float) -> None:
    batch = s.get(Batch, batch_id)
    if batch is None:
        return
    stats = dict(batch.stats or {})
    stats["work_seconds"] = round(stats.get("work_seconds", 0) + stage_seconds, 1)
    open_calls = s.exec(
        select(Call.id).where(
            Call.batch_id == batch_id, col(Call.status).in_([CallStatus.queued, CallStatus.running])
        )
    ).first()
    if open_calls is None and batch.status == BatchStatus.processing:
        batch.status = BatchStatus.done
        stats["finished_at"] = utcnow().isoformat()
    batch.stats = stats
    s.add(batch)
    s.commit()


def remove_raw_file(path: str | None) -> None:
    if path:
        p = Path(path)
        if p.is_dir():
            shutil.rmtree(p, ignore_errors=True)
        else:
            p.unlink(missing_ok=True)
