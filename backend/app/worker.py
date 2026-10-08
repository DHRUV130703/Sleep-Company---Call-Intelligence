"""Background worker — run with `python -m app.worker` (or `make worker`).

How it works:
- The `jobs` table is the queue. Each row = "run stage X for call Y".
- For every stage there are N "slots" (N = concurrency from .env). Each slot loops:
  claim one queued job atomically → run the stage handler → mark it done/failed.
- Jobs stuck in `running` for > 10 minutes (e.g. the worker was killed) are put back in the queue.
- Every few seconds the worker writes a heartbeat file; /api/health uses it to show "Worker: running".
"""

import asyncio
import contextlib
import fcntl
import logging
import os
import signal
import time
from datetime import datetime, timedelta

from sqlalchemy import select, update
from sqlmodel import Session, col

from app.config import get_settings
from app.db import get_engine, utcnow
from app.log import setup_logging
from app.models import CallStage, Job, JobStatus
from app.pipeline.stages import STAGE_HANDLERS, process_job

log = logging.getLogger("worker")

STALE_AFTER = timedelta(minutes=10)
HEARTBEAT_EVERY_S = 5
IDLE_SLEEP_S = 1.0


# ---------------------------------------------------------------------------
# Queue operations (plain functions so they are easy to test)
# ---------------------------------------------------------------------------


def claim_job(session: Session, stage: CallStage) -> Job | None:
    """Atomically take the oldest queued job for `stage`. Safe with several worker processes."""
    now = utcnow()
    next_id = (
        select(col(Job.id))
        .where(col(Job.status) == JobStatus.queued, col(Job.stage) == stage, col(Job.run_after) <= now)
        .order_by(col(Job.id))
        .limit(1)
        .scalar_subquery()
    )
    claimed_id = session.execute(
        update(Job)
        .where(col(Job.id) == next_id, col(Job.status) == JobStatus.queued)
        .values(status=JobStatus.running, locked_at=now, attempts=col(Job.attempts) + 1)
        .returning(col(Job.id))
    ).scalar_one_or_none()
    session.commit()
    return session.get(Job, claimed_id) if claimed_id is not None else None


def requeue_stale_jobs(session: Session, now: datetime | None = None) -> int:
    """Put jobs that have been `running` for too long back in the queue. Returns how many."""
    cutoff = (now or utcnow()) - STALE_AFTER
    result = session.execute(
        update(Job)
        .where(col(Job.status) == JobStatus.running, col(Job.locked_at) < cutoff)
        .values(status=JobStatus.queued, locked_at=None)
    )
    session.commit()
    return result.rowcount  # type: ignore[attr-defined, no-any-return]


def finish_job(session: Session, job_id: int, error: str | None = None) -> None:
    job = session.get(Job, job_id)
    if job is None:
        return
    job.status = JobStatus.failed if error else JobStatus.done
    job.last_error = error
    job.locked_at = None
    session.add(job)
    session.commit()


# ---------------------------------------------------------------------------
# Loops
# ---------------------------------------------------------------------------


def heartbeat_path():  # type: ignore[no-untyped-def]
    return get_settings().data_dir / "worker.heartbeat"


async def heartbeat_loop(stop: asyncio.Event) -> None:
    path = heartbeat_path()
    while not stop.is_set():
        path.write_text(utcnow().isoformat())
        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(stop.wait(), timeout=HEARTBEAT_EVERY_S)


async def stale_job_loop(stop: asyncio.Event) -> None:
    while not stop.is_set():
        with Session(get_engine()) as s:
            if n := requeue_stale_jobs(s):
                log.warning("re-queued stale jobs", extra={"count": n})
        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(stop.wait(), timeout=60)


async def slot_loop(stage: CallStage, stop: asyncio.Event) -> None:
    engine = get_engine()
    while not stop.is_set():
        with Session(engine) as s:
            job = await asyncio.to_thread(claim_job, s, stage)
        if job is None:
            await asyncio.sleep(IDLE_SLEEP_S)
            continue
        assert job.id is not None
        try:
            await process_job(job)  # records success, retry, skip or failure itself
        except Exception as exc:  # safety net: never let one bad job kill the slot
            log.exception("job crashed", extra={"job_id": job.id, "call_id": job.call_id, "stage": stage})
            with Session(engine) as s:
                finish_job(s, job.id, f"{type(exc).__name__}: {exc}")


async def retention_loop(stop: asyncio.Event) -> None:
    """Once an hour: delete raw recordings older than RAW_AUDIO_RETENTION_DAYS (transcripts are kept)."""
    while not stop.is_set():
        days = get_settings().raw_audio_retention_days
        if days > 0:
            removed = await asyncio.to_thread(purge_raw_audio, days)
            if removed:
                log.info("purged old raw audio", extra={"files": removed})
        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(stop.wait(), timeout=3600)


def purge_raw_audio(days: int) -> int:
    cutoff = time.time() - days * 86400
    removed = 0
    for folder in ("audio/raw", "uploads"):
        root = get_settings().data_dir / folder
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if path.is_file() and path.stat().st_mtime < cutoff:
                path.unlink(missing_ok=True)
                removed += 1
    return removed


def concurrency_for(stage: CallStage) -> int:
    s = get_settings()
    if stage == CallStage.transcribing and s.transcriber in ("faster_whisper", "mlx_whisper"):
        return 1  # local Whisper uses the whole machine: one call at a time (others show "Waiting")
    return {
        CallStage.downloading: s.concurrency_download,
        CallStage.transcribing: s.concurrency_transcribe,
        CallStage.analysing: s.concurrency_analyze,
    }.get(stage, 2)


async def run_worker(stop: asyncio.Event) -> None:
    get_settings().data_dir.mkdir(parents=True, exist_ok=True)
    with Session(get_engine()) as s:
        requeued = requeue_stale_jobs(s)
    cfg = get_settings()
    if cfg.transcriber in ("faster_whisper", "mlx_whisper"):
        log.info("loading Whisper model…", extra={"transcriber": cfg.transcriber})
        if cfg.transcriber == "faster_whisper":
            from app.providers import faster_whisper_local

            await asyncio.to_thread(faster_whisper_local.preload, cfg.whisper_model, cfg.whisper_compute_type)
        else:
            from app.providers import whisper_local

            await asyncio.to_thread(whisper_local.preload, cfg.mlx_whisper_model)
    log.info("worker started", extra={"stages": list(STAGE_HANDLERS), "requeued": requeued})

    tasks = [heartbeat_loop(stop), stale_job_loop(stop)]
    for stage in STAGE_HANDLERS:
        tasks += [slot_loop(stage, stop) for _ in range(concurrency_for(stage))]
    tasks.append(retention_loop(stop))
    await asyncio.gather(*tasks)
    log.info("worker stopped")


def single_instance_lock():  # type: ignore[no-untyped-def]
    """Only one worker may run. A second `make dev` would make two workers fight over the same calls."""
    path = get_settings().data_dir / "worker.lock"
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = path.open("w")
    try:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        log.error("another worker is already running — this one will exit. Only run `make dev` once.")
        raise SystemExit(1) from None
    handle.write(str(os.getpid()))
    handle.flush()
    return handle  # keep the file open: the lock lasts as long as this process


def main() -> None:
    setup_logging()
    _lock = single_instance_lock()  # noqa: F841
    stop = asyncio.Event()

    async def runner() -> None:
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, stop.set)
        await run_worker(stop)

    asyncio.run(runner())


if __name__ == "__main__":
    main()
