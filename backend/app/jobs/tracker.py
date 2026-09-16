"""In-process background job tracker (Phase 18, spec section 45).

"Long-running tasks must not block API requests. Architecture: HTTP
Request -> Job -> Queue -> Worker -> Experiment Executor -> Provenance
Collector -> Analysis Engine -> Database. Support: job ID, status,
progress, retries, cancellation, timeouts, concurrency limits,
idempotency, failure recovery. States: CREATED, QUEUED, PREPARING,
COLLECTING_PROVENANCE, EXECUTING, CAPTURING_ARTIFACTS, COMPARING,
ANALYZING, GENERATING_REPORT, COMPLETED, FAILED, CANCELLED."

The persisted `jobs.status` column is a Postgres native enum with only 6
values (CREATED/QUEUED/EXECUTING/COMPLETED/FAILED/CANCELLED) - extending
it needs a live-database migration this environment can't verify (no
reachable Postgres here, same limitation Phase 17 hit with Docker). So
the full 11-value spec state machine is tracked here, in-process, as
`JobStage` (a plain Python enum, not a DB column) and collapsed onto the
existing `JobStatus` only when `assemble_job` builds a persistable row -
see docs/BACKGROUND_JOBS.md for the full collapse table and rationale.

This module only builds the job/state-machine tracker itself - wiring a
real async worker loop that walks a job through Experiment Executor
(Phase 17) -> Provenance Collector -> Analysis Engine -> Database end to
end needs an HTTP/request context, which is Phase 19's job (FastAPI).
"""

from __future__ import annotations

import asyncio
import uuid
from contextlib import asynccontextmanager
from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from enum import Enum

from app.db.models.enums import JobStatus, JobType
from app.db.models.jobs import Job

JOB_TRACKER_VERSION = "1.0.0"


class JobStage(str, Enum):
    CREATED = "CREATED"
    QUEUED = "QUEUED"
    PREPARING = "PREPARING"
    COLLECTING_PROVENANCE = "COLLECTING_PROVENANCE"
    EXECUTING = "EXECUTING"
    CAPTURING_ARTIFACTS = "CAPTURING_ARTIFACTS"
    COMPARING = "COMPARING"
    ANALYZING = "ANALYZING"
    GENERATING_REPORT = "GENERATING_REPORT"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


_FORWARD_PIPELINE = [
    JobStage.CREATED,
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

TERMINAL_STAGES = frozenset({JobStage.COMPLETED, JobStage.FAILED, JobStage.CANCELLED})

JOB_STAGE_TRANSITIONS: dict[JobStage, frozenset[JobStage]] = {}
for _i, _stage in enumerate(_FORWARD_PIPELINE):
    _next_forward = {_FORWARD_PIPELINE[_i + 1]} if _i + 1 < len(_FORWARD_PIPELINE) else set()
    if _stage in TERMINAL_STAGES:
        JOB_STAGE_TRANSITIONS[_stage] = frozenset()
    else:
        JOB_STAGE_TRANSITIONS[_stage] = frozenset(_next_forward | {JobStage.FAILED, JobStage.CANCELLED})
JOB_STAGE_TRANSITIONS[JobStage.FAILED] = frozenset()
JOB_STAGE_TRANSITIONS[JobStage.CANCELLED] = frozenset()

_STAGE_TO_STATUS: dict[JobStage, JobStatus] = {
    JobStage.CREATED: JobStatus.CREATED,
    JobStage.QUEUED: JobStatus.QUEUED,
    JobStage.PREPARING: JobStatus.EXECUTING,
    JobStage.COLLECTING_PROVENANCE: JobStatus.EXECUTING,
    JobStage.EXECUTING: JobStatus.EXECUTING,
    JobStage.CAPTURING_ARTIFACTS: JobStatus.EXECUTING,
    JobStage.COMPARING: JobStatus.EXECUTING,
    JobStage.ANALYZING: JobStatus.EXECUTING,
    JobStage.GENERATING_REPORT: JobStatus.EXECUTING,
    JobStage.COMPLETED: JobStatus.COMPLETED,
    JobStage.FAILED: JobStatus.FAILED,
    JobStage.CANCELLED: JobStatus.CANCELLED,
}


class InvalidJobTransitionError(Exception):
    pass


class JobNotFoundError(Exception):
    pass


@dataclass(frozen=True)
class JobRecord:
    job_id: uuid.UUID
    job_type: JobType
    stage: JobStage
    created_at: datetime
    progress_pct: int = 0
    retry_count: int = 0
    error_message: str | None = None
    related_run_id: uuid.UUID | None = None
    related_comparison_id: uuid.UUID | None = None
    idempotency_key: str | None = None
    deadline: datetime | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None


class JobTracker:
    def __init__(self, max_concurrent: int = 4) -> None:
        self._jobs: dict[uuid.UUID, JobRecord] = {}
        self._idempotency_index: dict[str, uuid.UUID] = {}
        self._semaphore = asyncio.Semaphore(max_concurrent)

    def create_job(
        self,
        job_type: JobType,
        *,
        related_run_id: uuid.UUID | None = None,
        related_comparison_id: uuid.UUID | None = None,
        idempotency_key: str | None = None,
        timeout_seconds: int | None = None,
    ) -> uuid.UUID:
        if idempotency_key is not None and idempotency_key in self._idempotency_index:
            return self._idempotency_index[idempotency_key]

        job_id = uuid.uuid4()
        now = datetime.now(timezone.utc)
        deadline = now + timedelta(seconds=timeout_seconds) if timeout_seconds is not None else None
        record = JobRecord(
            job_id=job_id,
            job_type=job_type,
            stage=JobStage.CREATED,
            related_run_id=related_run_id,
            related_comparison_id=related_comparison_id,
            idempotency_key=idempotency_key,
            deadline=deadline,
            created_at=now,
        )
        self._jobs[job_id] = record
        if idempotency_key is not None:
            self._idempotency_index[idempotency_key] = job_id
        return job_id

    def get(self, job_id: uuid.UUID) -> JobRecord:
        try:
            return self._jobs[job_id]
        except KeyError:
            raise JobNotFoundError(str(job_id)) from None

    def transition(self, job_id: uuid.UUID, new_stage: JobStage) -> JobRecord:
        record = self.get(job_id)
        allowed = JOB_STAGE_TRANSITIONS[record.stage]
        if new_stage not in allowed:
            raise InvalidJobTransitionError(f"cannot transition job {job_id} from {record.stage} to {new_stage}")

        now = datetime.now(timezone.utc)
        updates: dict = {"stage": new_stage}
        if record.stage == JobStage.CREATED and record.started_at is None:
            updates["started_at"] = now
        if new_stage in TERMINAL_STAGES:
            updates["finished_at"] = now

        updated = replace(record, **updates)
        self._jobs[job_id] = updated
        return updated

    def update_progress(self, job_id: uuid.UUID, pct: int) -> JobRecord:
        if not 0 <= pct <= 100:
            raise ValueError(f"progress_pct must be between 0 and 100, got {pct}")
        record = self.get(job_id)
        updated = replace(record, progress_pct=pct)
        self._jobs[job_id] = updated
        return updated

    def cancel(self, job_id: uuid.UUID) -> JobRecord:
        record = self.get(job_id)
        if record.stage in TERMINAL_STAGES:
            raise InvalidJobTransitionError(f"cannot cancel job {job_id} already in terminal stage {record.stage}")
        return self.transition(job_id, JobStage.CANCELLED)

    def record_failure(self, job_id: uuid.UUID, error_message: str) -> JobRecord:
        record = self.get(job_id)
        if record.stage in TERMINAL_STAGES:
            raise InvalidJobTransitionError(f"cannot fail job {job_id} already in terminal stage {record.stage}")
        updated = self.transition(job_id, JobStage.FAILED)
        updated = replace(updated, error_message=error_message)
        self._jobs[job_id] = updated
        return updated

    def retry(self, job_id: uuid.UUID) -> JobRecord:
        record = self.get(job_id)
        if record.stage != JobStage.FAILED:
            raise InvalidJobTransitionError(f"cannot retry job {job_id} from non-FAILED stage {record.stage}")
        updated = replace(
            record,
            stage=JobStage.QUEUED,
            retry_count=record.retry_count + 1,
            error_message=None,
            finished_at=None,
        )
        self._jobs[job_id] = updated
        return updated

    def is_overdue(self, job_id: uuid.UUID) -> bool:
        record = self.get(job_id)
        if record.deadline is None:
            return False
        return datetime.now(timezone.utc) > record.deadline

    @asynccontextmanager
    async def slot(self):
        async with self._semaphore:
            yield

    def assemble_job(self, job_id: uuid.UUID) -> Job:
        """Build an unattached `Job` ORM row from the tracked in-process
        state. The caller is responsible for `session.add()`/`commit()`
        once a DB session exists (Phase 19), mirroring
        `app.comparison.engine.assemble_comparison`."""
        record = self.get(job_id)
        return Job(
            id=record.job_id,
            job_type=record.job_type,
            related_run_id=record.related_run_id,
            related_comparison_id=record.related_comparison_id,
            status=_STAGE_TO_STATUS[record.stage],
            progress_pct=record.progress_pct,
            error_message=record.error_message,
            started_at=record.started_at,
            finished_at=record.finished_at,
        )
