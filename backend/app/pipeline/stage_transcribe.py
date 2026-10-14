"""Stage 3: transcribe (+ speaker roles), with a transcript cache.

AssemblyAI is used in two short steps so no request ever waits on it (Vercel stops requests after 5 min):
    1. start  → upload the recording, remember AssemblyAI's job id (stored as a small file)
    2. check  → one look; if it isn't ready, StageWait puts the job back in the queue for a few seconds
Other speech-to-text providers (local Whisper, OpenAI, Gemini) transcribe in one go, long calls in pieces.
"""

import json
import tempfile
from pathlib import Path
from typing import Any

from sqlmodel import Session, select

from app import storage
from app.config import get_settings
from app.db import get_engine
from app.errors import AppError, ErrorCode
from app.models import Batch, Call, CallStage, CallStatus, Transcript, TranscriptCache, TranscriptScript
from app.pipeline import audio
from app.pipeline.analysis import assign_speakers, provider_stage_error
from app.pipeline.errors import StageError, StageWait
from app.pipeline.events import emit
from app.providers import get_transcriber
from app.providers.assemblyai import AssemblyAITranscriber
from app.providers.base import ProviderError

CHUNK_OVERLAP_S = 5
CHECK_AGAIN_S = 5  # how soon to look again while AssemblyAI is still transcribing


def _load(session: Session, call_id: int) -> Call:
    call = session.get(Call, call_id)
    if call is None:
        raise StageError(ErrorCode.NOT_FOUND)
    return call


async def stage_transcribe(call_id: int) -> CallStage | None:
    settings = get_settings()
    with Session(get_engine()) as s:
        call = _load(s, call_id)
        if s.exec(select(Transcript).where(Transcript.call_id == call_id)).first():
            return CallStage.analysing
        emit(s, call, stage=CallStage.transcribing, status=CallStatus.running, message="Transcribing")
        sha, norm_key, duration = call.audio_sha256, call.audio_path or "", call.duration_s or 0
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
    raw_key = f"transcripts_raw/{sha or call_id}-{transcriber.name}.json"
    stepwise = _stepwise_transcriber()
    if storage.exists(raw_key):
        raw_segments = json.loads(storage.read_bytes(raw_key))
    else:
        if not storage.exists(norm_key):
            raise StageError(ErrorCode.NOTHING_TO_PROCESS, detail="Recording file is missing")
        try:
            if stepwise:
                raw_segments = await _transcribe_stepwise(stepwise, norm_key, raw_key)  # may raise StageWait
            else:
                with storage.local_copy(norm_key) as norm:
                    raw_segments = await _transcribe_in_chunks(
                        norm, duration, str(script), settings.chunk_minutes * 60, call_id
                    )
        except ProviderError as exc:
            raise provider_stage_error(exc) from exc
        storage.put_bytes(raw_key, json.dumps(raw_segments, ensure_ascii=False).encode(), "application/json")
        storage.delete_file(_pending_key(raw_key))
    if not raw_segments:
        raise StageError(ErrorCode.SILENT, skip=True)

    labelled = await assign_speakers(raw_segments, str(script))
    segments = [{**seg, "i": i} for i, seg in enumerate(labelled)]
    roles = {seg["speaker"]: seg["role"] for seg in segments}
    used = stepwise or transcriber.last_used
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


def _stepwise_transcriber() -> AssemblyAITranscriber | None:
    """AssemblyAI (with no fallback provider) runs in start/check steps; anything else in one go."""
    t = get_transcriber()
    if t.primary_name != "assemblyai" or t.fallback_name:
        return None
    try:
        built = t.build_primary()
    except AppError:  # e.g. no API key: the one-go path below turns it into a clear message
        return None
    return built if isinstance(built, AssemblyAITranscriber) else None


def _pending_key(raw_key: str) -> str:
    """Where AssemblyAI's job id is kept while it transcribes, e.g. transcripts_pending/<sha>-assemblyai.txt."""
    return raw_key.replace("transcripts_raw/", "transcripts_pending/").removesuffix(".json") + ".txt"


async def _transcribe_stepwise(t: AssemblyAITranscriber, norm_key: str, raw_key: str) -> list[dict[str, Any]]:
    pending = _pending_key(raw_key)
    if not storage.exists(pending):
        with storage.local_copy(
            norm_key
        ) as norm:  # the whole recording: AssemblyAI handles long calls itself
            job_id = await t.start(norm)
        storage.put_bytes(pending, job_id.encode(), "text/plain")
        raise StageWait(CHECK_AGAIN_S, "Transcribing — sent to AssemblyAI")
    job_id = storage.read_bytes(pending).decode()
    result = await t.check(job_id)
    if result is None:
        raise StageWait(CHECK_AGAIN_S, "Transcribing — AssemblyAI is working on it")
    return [seg.model_dump() for seg in result.segments if seg.text.strip()]
