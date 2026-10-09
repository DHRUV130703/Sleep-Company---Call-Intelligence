from datetime import timedelta

from app.db import utcnow
from app.models import AgentType, AgentTypeMode, Batch, Call, CallStage, Job, JobStatus, SourceType
from app.worker import claim_job, finish_job, requeue_stale_jobs


def _make_call(session) -> int:
    batch = Batch(name="t", source_type=SourceType.links, agent_type_mode=AgentTypeMode.ai)
    session.add(batch)
    session.commit()
    call = Call(batch_id=batch.id, label="A1", agent_type=AgentType.ai)
    session.add(call)
    session.commit()
    return call.id


def test_claims_oldest_queued_job_for_the_stage_only(session):
    call_id = _make_call(session)
    session.add_all(
        [
            Job(call_id=call_id, stage=CallStage.transcribing),
            Job(call_id=call_id, stage=CallStage.downloading),
            Job(call_id=call_id, stage=CallStage.downloading),
        ]
    )
    session.commit()

    job = claim_job(session, CallStage.downloading)
    assert job is not None and job.id == 2
    assert job.status == JobStatus.running and job.attempts == 1 and job.locked_at is not None

    assert claim_job(session, CallStage.downloading).id == 3
    assert claim_job(session, CallStage.downloading) is None  # nothing left for this stage


def test_a_job_is_never_claimed_twice(session):
    call_id = _make_call(session)
    session.add(Job(call_id=call_id, stage=CallStage.analysing))
    session.commit()
    assert claim_job(session, CallStage.analysing) is not None
    assert claim_job(session, CallStage.analysing) is None


def test_future_jobs_wait_until_run_after(session):
    call_id = _make_call(session)
    session.add(Job(call_id=call_id, stage=CallStage.analysing, run_after=utcnow() + timedelta(minutes=5)))
    session.commit()
    assert claim_job(session, CallStage.analysing) is None


def test_stale_running_jobs_are_requeued(session):
    call_id = _make_call(session)
    session.add(Job(call_id=call_id, stage=CallStage.preparing))
    session.commit()
    job = claim_job(session, CallStage.preparing)

    assert requeue_stale_jobs(session) == 0  # just claimed → not stale
    assert requeue_stale_jobs(session, now=utcnow() + timedelta(minutes=11)) == 1
    session.refresh(job)
    assert job.status == JobStatus.queued and job.locked_at is None


def test_finish_job_records_errors(session):
    call_id = _make_call(session)
    session.add(Job(call_id=call_id, stage=CallStage.preparing))
    session.commit()
    job = claim_job(session, CallStage.preparing)
    finish_job(session, job.id, error="boom")
    session.refresh(job)
    assert job.status == JobStatus.failed and job.last_error == "boom"


def test_queue_check_sees_only_jobs_that_are_due(session):
    from app.worker import has_queued_jobs

    assert has_queued_jobs(session) is False
    call_id = _make_call(session)
    session.add(Job(call_id=call_id, stage=CallStage.analysing, run_after=utcnow() + timedelta(minutes=5)))
    session.commit()
    assert has_queued_jobs(session) is False  # a retry waiting for later doesn't wake anyone
    session.add(Job(call_id=call_id, stage=CallStage.preparing))
    session.commit()
    assert has_queued_jobs(session) is True


async def test_idle_slots_sleep_until_nudged():
    import asyncio
    import time

    from app.worker import Wakeup

    wakeup = Wakeup()
    started = time.monotonic()
    waiter = asyncio.create_task(wakeup.wait(timeout=30))
    await asyncio.sleep(0.05)
    await wakeup.nudge()
    await waiter
    assert time.monotonic() - started < 1  # woke on the nudge, not after the 30 s timeout
