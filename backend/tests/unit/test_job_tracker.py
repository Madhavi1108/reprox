import asyncio
from datetime import datetime, timedelta, timezone

import pytest

from app.db.models.enums import JobStatus, JobType
from app.jobs.tracker import (
    JOB_STAGE_TRANSITIONS,
    TERMINAL_STAGES,
    InvalidJobTransitionError,
    JobNotFoundError,
    JobStage,
    JobTracker,
    _STAGE_TO_STATUS,
)

FULL_PIPELINE = [
    JobStage.QUEUED,
    JobStage.PREPARING,
    JobStage.COLLECTING_PROVENANCE,
    JobStage.EXECUTING,
    JobStage.CAPTURING_ARTIFACTS,
    JobStage.COMPARING,
    JobStage.ANALYZING,
    JobStage.GENERATING_REPORT,
    JobStage.COMPLETED,
]


def test_full_forward_pipeline_reaches_completed():
    tracker = JobTracker()
    job_id = tracker.create_job(JobType.RUN_EXPERIMENT)

    for stage in FULL_PIPELINE:
        record = tracker.transition(job_id, stage)

    assert record.stage == JobStage.COMPLETED
    assert record.started_at is not None
    assert record.finished_at is not None


def test_illegal_transition_raises():
    tracker = JobTracker()
    job_id = tracker.create_job(JobType.RUN_EXPERIMENT)
    with pytest.raises(InvalidJobTransitionError):
        tracker.transition(job_id, JobStage.COMPLETED)  # can't skip straight there


def test_terminal_stages_reject_further_transitions():
    tracker = JobTracker()
    job_id = tracker.create_job(JobType.RUN_EXPERIMENT)
    tracker.transition(job_id, JobStage.QUEUED)
    tracker.cancel(job_id)

    with pytest.raises(InvalidJobTransitionError):
        tracker.transition(job_id, JobStage.PREPARING)
    with pytest.raises(InvalidJobTransitionError):
        tracker.cancel(job_id)
    with pytest.raises(InvalidJobTransitionError):
        tracker.record_failure(job_id, "too late")


def test_cancel_from_mid_pipeline_stage():
    tracker = JobTracker()
    job_id = tracker.create_job(JobType.RUN_EXPERIMENT)
    tracker.transition(job_id, JobStage.QUEUED)
    tracker.transition(job_id, JobStage.PREPARING)

    record = tracker.cancel(job_id)
    assert record.stage == JobStage.CANCELLED
    assert record.finished_at is not None


def test_record_failure_from_mid_pipeline_stage():
    tracker = JobTracker()
    job_id = tracker.create_job(JobType.RUN_EXPERIMENT)
    tracker.transition(job_id, JobStage.QUEUED)
    tracker.transition(job_id, JobStage.PREPARING)
    tracker.transition(job_id, JobStage.COLLECTING_PROVENANCE)
    tracker.transition(job_id, JobStage.EXECUTING)

    record = tracker.record_failure(job_id, "sandbox crashed")
    assert record.stage == JobStage.FAILED
    assert record.error_message == "sandbox crashed"


def test_retry_only_valid_from_failed():
    tracker = JobTracker()
    job_id = tracker.create_job(JobType.RUN_EXPERIMENT)
    tracker.transition(job_id, JobStage.QUEUED)

    with pytest.raises(InvalidJobTransitionError):
        tracker.retry(job_id)

    tracker.record_failure(job_id, "boom")
    record = tracker.retry(job_id)

    assert record.stage == JobStage.QUEUED
    assert record.retry_count == 1
    assert record.error_message is None
    assert record.finished_at is None


def test_progress_validation():
    tracker = JobTracker()
    job_id = tracker.create_job(JobType.RUN_EXPERIMENT)
    record = tracker.update_progress(job_id, 50)
    assert record.progress_pct == 50

    with pytest.raises(ValueError):
        tracker.update_progress(job_id, 101)
    with pytest.raises(ValueError):
        tracker.update_progress(job_id, -1)


def test_idempotency_key_returns_same_job():
    tracker = JobTracker()
    job_id_1 = tracker.create_job(JobType.RUN_EXPERIMENT, idempotency_key="run-42")
    job_id_2 = tracker.create_job(JobType.RUN_EXPERIMENT, idempotency_key="run-42")
    assert job_id_1 == job_id_2
    assert len(tracker._jobs) == 1


def test_different_idempotency_keys_create_separate_jobs():
    tracker = JobTracker()
    job_id_1 = tracker.create_job(JobType.RUN_EXPERIMENT, idempotency_key="a")
    job_id_2 = tracker.create_job(JobType.RUN_EXPERIMENT, idempotency_key="b")
    assert job_id_1 != job_id_2


def test_is_overdue():
    tracker = JobTracker()
    job_id = tracker.create_job(JobType.RUN_EXPERIMENT, timeout_seconds=10)
    assert tracker.is_overdue(job_id) is False

    # Force the deadline into the past to simulate elapsed time.
    from dataclasses import replace

    record = tracker.get(job_id)
    tracker._jobs[job_id] = replace(record, deadline=datetime.now(timezone.utc) - timedelta(seconds=1))
    assert tracker.is_overdue(job_id) is True


def test_job_not_found_raises():
    tracker = JobTracker()
    with pytest.raises(JobNotFoundError):
        tracker.get(__import__("uuid").uuid4())


def test_stage_to_status_collapse_is_exhaustive_and_correct():
    for stage in JobStage:
        assert stage in _STAGE_TO_STATUS
    assert _STAGE_TO_STATUS[JobStage.CREATED] == JobStatus.CREATED
    assert _STAGE_TO_STATUS[JobStage.QUEUED] == JobStatus.QUEUED
    for in_progress in (
        JobStage.PREPARING,
        JobStage.COLLECTING_PROVENANCE,
        JobStage.EXECUTING,
        JobStage.CAPTURING_ARTIFACTS,
        JobStage.COMPARING,
        JobStage.ANALYZING,
        JobStage.GENERATING_REPORT,
    ):
        assert _STAGE_TO_STATUS[in_progress] == JobStatus.EXECUTING
    assert _STAGE_TO_STATUS[JobStage.COMPLETED] == JobStatus.COMPLETED
    assert _STAGE_TO_STATUS[JobStage.FAILED] == JobStatus.FAILED
    assert _STAGE_TO_STATUS[JobStage.CANCELLED] == JobStatus.CANCELLED


def test_assemble_job_builds_unattached_orm_row():
    tracker = JobTracker()
    job_id = tracker.create_job(JobType.RUN_EXPERIMENT)
    tracker.transition(job_id, JobStage.QUEUED)
    tracker.transition(job_id, JobStage.PREPARING)
    tracker.update_progress(job_id, 30)

    job = tracker.assemble_job(job_id)

    assert job.id == job_id
    assert job.job_type == JobType.RUN_EXPERIMENT
    assert job.status == JobStatus.EXECUTING  # PREPARING collapses to EXECUTING
    assert job.progress_pct == 30


def test_terminal_stages_have_no_outgoing_transitions():
    for stage in TERMINAL_STAGES:
        assert JOB_STAGE_TRANSITIONS[stage] == frozenset()


async def test_concurrency_limit_blocks_beyond_max_concurrent():
    tracker = JobTracker(max_concurrent=2)
    active = 0
    max_observed = 0
    release_event = asyncio.Event()

    async def worker():
        nonlocal active, max_observed
        async with tracker.slot():
            active += 1
            max_observed = max(max_observed, active)
            await release_event.wait()
            active -= 1

    tasks = [asyncio.create_task(worker()) for _ in range(4)]
    await asyncio.sleep(0.05)  # let the first 2 acquire their slots

    assert active == 2
    assert max_observed == 2

    release_event.set()
    await asyncio.gather(*tasks)
    assert active == 0
