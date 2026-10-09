"""Background worker — run with `python -m app.worker` (or `make worker`).

How it works:
- The `jobs` table is the queue. Each row = "run stage X for call Y".
- For every stage there are N "slots" (N = concurrency from .env). Each slot loops:
  claim one queued job atomically → run the stage handler → mark it done/failed.
- Idle slots don't query the database: one cheap check every few seconds wakes them when work is queued
  (a cloud database is billed per request), and finishing a stage wakes them for the next one.
- Jobs stuck in `running` for > 10 minutes (e.g. the worker was killed) are put back in the queue.
- Every few seconds the worker writes a heartbeat row (worker_heartbeats); /api/health uses it to
  show "Worker: running".
"""

import asyncio
import contextlib
import fcntl
import logging
import os
import signal
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

from sqlalchemy import select, update
from sqlmodel import Session, col

from app import storage
from app.config import get_settings
from app.db import get_engine, utcnow
from app.log import setup_logging
from app.models import CallStage, Job, JobStatus, WorkerHeartbeat
from app.pipeline.stages import STAGE_HANDLERS, process_job

log = logging.getLogger("worker")

STALE_AFTER = timedelta(minutes=10)
HEARTBEAT_EVERY_S = 15
QUEUE_CHECK_S = 5.0  # how often one cheap query checks for new work (uploads from the API, retries)
IDLE_WAIT_S = 60.0  # an idle slot also looks for work at least this often, just in case
DB_RETRY_S = 5.0  # wait after the database couldn't be reached


class Wakeup:
    """Lets idle slots sleep without querying the database. A cloud database is billed per request:
    10 slots each asking "any work?" every second would cost far more than the actual work."""

    def __init__(self) -> None:
        self._cond = asyncio.Condition()

    async def wait(self, timeout: float) -> None:
        async with self._cond:
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(self._cond.wait(), timeout)

    async def nudge(self) -> None:
        async with self._cond:
            self._cond.notify_all()


def has_queued_jobs(session: Session) -> bool:
    now = utcnow()
    first = session.execute(
        select(col(Job.id)).where(col(Job.status) == JobStatus.queued, col(Job.run_after) <= now).limit(1)
    ).first()
    return first is not None


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


def write_heartbeat() -> None:
    with Session(get_engine()) as s:
        beat = s.get(WorkerHeartbeat, "worker") or WorkerHeartbeat(name="worker")
        beat.beat_at = utcnow()
        s.add(beat)
        s.commit()


def last_heartbeat() -> datetime | None:
    with Session(get_engine()) as s:
        beat = s.get(WorkerHeartbeat, "worker")
        return beat.beat_at if beat else None


async def heartbeat_loop(stop: asyncio.Event) -> None:
    while not stop.is_set():
        try:
            await asyncio.to_thread(write_heartbeat)
        except Exception:  # a dropped connection must not stop the worker
            log.warning("heartbeat failed", exc_info=True)
        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(stop.wait(), timeout=HEARTBEAT_EVERY_S)


async def stale_job_loop(stop: asyncio.Event) -> None:
    while not stop.is_set():
        try:
            with Session(get_engine()) as s:
                if n := requeue_stale_jobs(s):
                    log.warning("re-queued stale jobs", extra={"count": n})
        except Exception:
            log.warning("database unreachable; will retry", exc_info=True)
        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(stop.wait(), timeout=60)


async def queue_check_loop(wakeup: Wakeup, stop: asyncio.Event) -> None:
    """One cheap query every few seconds; wakes the slots only when there is queued work."""
    while not stop.is_set():
        try:
            with Session(get_engine()) as s:
                found = await asyncio.to_thread(has_queued_jobs, s)
            if found:
                await wakeup.nudge()
        except Exception:
            log.warning("database unreachable; will retry", exc_info=True)
        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(stop.wait(), timeout=QUEUE_CHECK_S)


async def slot_loop(stage: CallStage, stop: asyncio.Event, wakeup: Wakeup) -> None:
    engine = get_engine()
    while not stop.is_set():
        try:
            with Session(engine) as s:
                job = await asyncio.to_thread(claim_job, s, stage)
        except Exception:  # cloud database briefly unreachable: wait and try again, never exit
            log.warning("database unreachable; retrying", extra={"stage": stage}, exc_info=True)
            await asyncio.sleep(DB_RETRY_S)
            continue
        if job is None:
            await wakeup.wait(IDLE_WAIT_S)  # no query until there is work (or a minute passes)
            continue
        assert job.id is not None
        try:
            await process_job(job)  # records success, retry, skip or failure itself
        except Exception as exc:  # safety net: never let one bad job kill the slot
            log.exception("job crashed", extra={"job_id": job.id, "call_id": job.call_id, "stage": stage})
            try:
                with Session(engine) as s:
                    finish_job(s, job.id, f"{type(exc).__name__}: {exc}")
            except Exception:  # the job stays "running"; stale_job_loop re-queues it after 10 minutes
                log.warning("couldn't record the failed job", exc_info=True)
        await wakeup.nudge()  # the call's next stage is queued now: start it straight away


async def retention_loop(stop: asyncio.Event) -> None:
    """Once an hour: delete raw recordings older than RAW_AUDIO_RETENTION_DAYS (transcripts are kept)."""
    while not stop.is_set():
        days = get_settings().raw_audio_retention_days
        if days > 0:
            try:
                removed = await asyncio.to_thread(purge_raw_audio, days)
                if removed:
                    log.info("purged old raw audio", extra={"files": removed})
            except Exception:
                log.warning("retention cleanup failed; will retry next hour", exc_info=True)
        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(stop.wait(), timeout=3600)


def purge_raw_audio(days: int) -> int:
    """Delete original recordings and unfinished uploads older than `days` (normalised audio is kept)."""
    cutoff = utcnow() - timedelta(days=days)
    removed = 0
    for prefix in ("audio/raw/", "uploads/"):
        for key in storage.keys(prefix, older_than=cutoff):
            storage.delete_file(key)
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
    requeued = 0
    try:
        with Session(get_engine()) as s:
            requeued = requeue_stale_jobs(s)
    except Exception:  # stale_job_loop tries again in a minute
        log.warning("database unreachable at start; continuing", exc_info=True)
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

    wakeup = Wakeup()
    tasks = [heartbeat_loop(stop), stale_job_loop(stop), queue_check_loop(wakeup, stop)]
    for stage in STAGE_HANDLERS:
        tasks += [slot_loop(stage, stop, wakeup) for _ in range(concurrency_for(stage))]
    tasks.append(retention_loop(stop))
    await asyncio.gather(*tasks)
    log.info("worker stopped")


def single_instance_lock():  # type: ignore[no-untyped-def]
    """Only one worker per machine. A second `make dev` would make two workers fight over the same calls.
    The lock file lives in the system temp folder (it holds no data)."""
    path = Path(tempfile.gettempdir()) / "limezip-worker.lock"
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
