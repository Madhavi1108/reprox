"""GET /jobs, GET /jobs/{id} (Phase 19).

Reads from the in-process `JobTracker` (Phase 18), not the `jobs` DB
table - the tracker is the live source of truth for in-flight job state
in this MVP (no queue/worker process boundary to cross), and does not
survive an API server restart. See docs/BACKGROUND_JOBS.md.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends

from app.core.errors import NotFoundError
from app.jobs.orchestrator import get_job_tracker
from app.jobs.tracker import JobNotFoundError, JobRecord, JobTracker, stage_to_status
from app.schemas.common import Page
from app.schemas.job import JobRead

router = APIRouter(tags=["jobs"])


def _to_read(record: JobRecord) -> JobRead:
    return JobRead(
        id=record.job_id,
        job_type=record.job_type,
        related_run_id=record.related_run_id,
        related_comparison_id=record.related_comparison_id,
        status=stage_to_status(record.stage),
        progress_pct=record.progress_pct,
        error_message=record.error_message,
        created_at=record.created_at,
        started_at=record.started_at,
        finished_at=record.finished_at,
    )


@router.get("/jobs", response_model=Page[JobRead])
def list_jobs(tracker: JobTracker = Depends(get_job_tracker), limit: int = 20, offset: int = 0) -> Page[JobRead]:
    all_jobs = sorted(tracker.list_jobs(), key=lambda r: r.created_at, reverse=True)
    total = len(all_jobs)
    page_items = all_jobs[offset : offset + limit]
    return Page(items=[_to_read(r) for r in page_items], total=total, limit=limit, offset=offset)


@router.get("/jobs/{job_id}", response_model=JobRead)
def get_job(job_id: uuid.UUID, tracker: JobTracker = Depends(get_job_tracker)) -> JobRead:
    try:
        record = tracker.get(job_id)
    except JobNotFoundError:
        raise NotFoundError(f"job {job_id} not found") from None
    return _to_read(record)
