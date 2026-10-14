"""Processing inside web requests ("ticks"), for hosting without a background worker (Vercel).

While someone has the app open, the page keeps calling POST /api/process/tick. Each tick runs ONE step
of one call (download, prepare, transcribe-start / transcribe-check, analyse) within TICK_TIME_LIMIT_S,
well under Vercel's 5-minute limit. The queue, retries and per-stage limits are the same as the worker's,
so the worker (`make worker`) and ticks can run at the same time without doing anything twice.

Turned on with PROCESS_IN_REQUESTS=true (set on Vercel). Off locally, where the worker runs.
"""

from datetime import datetime
from typing import Any

from sqlalchemy import func
from sqlmodel import Session, col, select

from app.db import utcnow
from app.models import CallStage, Job, JobStatus
from app.pipeline.stages import process_job
from app.worker import claim_job, concurrency_for, requeue_stale_jobs

TICK_TIME_LIMIT_S = 240  # leaves a minute of Vercel's 300 s for saving results and the response
# Finish calls that are furthest along first, so results appear as early as possible.
STAGE_ORDER = (CallStage.analysing, CallStage.transcribing, CallStage.preparing, CallStage.downloading)


def _running(session: Session, stage: CallStage) -> int:
    q = (
        select(func.count())
        .select_from(Job)
        .where(col(Job.status) == JobStatus.running, col(Job.stage) == stage)
    )
    return int(session.exec(q).one())


def claim_next_job(session: Session) -> Job | None:
    """The next due job, respecting each stage's limit (e.g. one AI analysis at a time on a free plan)."""
    for stage in STAGE_ORDER:
        if _running(session, stage) < concurrency_for(stage):
            job = claim_job(session, stage)
            if job is not None:
                return job
    return None


def queue_state(session: Session) -> dict[str, Any]:
    """How much work is left, and when the next waiting job is due (seconds), for the page's next tick."""
    now = utcnow()
    queued = session.exec(
        select(func.count(), func.min(Job.run_after)).where(col(Job.status) == JobStatus.queued)
    ).one()
    running = session.exec(
        select(func.count()).select_from(Job).where(col(Job.status) == JobStatus.running)
    ).one()
    next_at: datetime | None = queued[1]
    if next_at is not None and next_at.tzinfo is None:
        next_at = next_at.replace(tzinfo=now.tzinfo)
    return {
        "queued": int(queued[0]),
        "running": int(running),
        "next_in_s": max(0.0, (next_at - now).total_seconds()) if next_at else None,
    }


async def tick(session: Session) -> dict[str, Any]:
    requeue_stale_jobs(session)  # a step cut off by a crash or timeout goes back in the queue
    job = claim_next_job(session)
    processed = None
    if job is not None:
        await process_job(job, time_limit_s=TICK_TIME_LIMIT_S)
        processed = {"call_id": job.call_id, "stage": job.stage}
    return {"processed": processed, **queue_state(session)}
