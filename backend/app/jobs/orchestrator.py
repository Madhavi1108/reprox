"""Wires Phase 17 (sandbox) + Phase 18 (job tracker) into a run's actual
execution (Phase 19).

This is real, callable code - not a stub - but it has never been
exercised end to end in this environment, since that requires a reachable
Docker daemon and Postgres, neither of which exists here (see
docs/EXECUTION_SANDBOX.md and docs/BACKGROUND_JOBS.md for the same
limitation on the two phases this module connects). `SandboxRunner`
itself already degrades gracefully when Docker is unreachable (it reports
`SandboxRunStatus.ERROR` rather than raising), so calling this against no
daemon fails predictably and safely rather than crashing the request.

A single process-wide `JobTracker` is used (`get_job_tracker()`) since
Phase 18's tracker is in-process by design (spec's own approved
substitution for a real queue) - it does not survive an API server
restart, which is an accepted MVP limitation, not an oversight.
"""

from __future__ import annotations

import uuid
from functools import lru_cache
from pathlib import Path

from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.models.core import Experiment, ExperimentRun
from app.db.models.enums import RunStatus
from app.jobs.tracker import JobStage, JobTracker
from app.sandbox.runner import SandboxLimits, SandboxRunner, SandboxRunRequest, SandboxRunStatus


@lru_cache
def get_job_tracker() -> JobTracker:
    return JobTracker()


def build_sandbox_request(experiment: Experiment, run_id: uuid.UUID) -> SandboxRunRequest:
    """Pure helper (no DB/Docker access) so the request-construction logic
    is unit-testable without either. Convention: each workload type has a
    matching subdirectory under `settings.workloads_dir`; each run gets its
    own output directory under `settings.artifacts_dir`."""
    settings = get_settings()
    return SandboxRunRequest(
        run_id=run_id,
        image=settings.sandbox_image,
        workload_dir=Path(settings.workloads_dir) / experiment.workload_type,
        output_dir=Path(settings.artifacts_dir) / str(run_id),
        entrypoint_script=experiment.entrypoint_script,
        limits=SandboxLimits.from_settings(settings),
    )


def execute_experiment_run(
    db: Session, run_id: uuid.UUID, job_id: uuid.UUID, tracker: JobTracker, runner: SandboxRunner | None = None
) -> None:
    """Runs one experiment inside the sandbox and updates both the
    `ExperimentRun` row and the job's tracked stage. Intended to be called
    as a FastAPI `BackgroundTasks` callback after the triggering request
    has already returned - never called synchronously from within a
    request handler, since a sandbox run can take up to
    `sandbox_timeout_seconds`."""
    run = db.get(ExperimentRun, run_id)
    experiment = db.get(Experiment, run.experiment_id)

    # Job stages walk the full spec pipeline sequentially (JOB_STAGE_TRANSITIONS
    # only allows the next stage or FAILED/CANCELLED, never skipping ahead).
    # COLLECTING_PROVENANCE/CAPTURING_ARTIFACTS/COMPARING/ANALYZING/
    # GENERATING_REPORT are no-ops for a bare run-experiment job in this MVP
    # (provenance is supplied externally at compare time, not captured here;
    # no automatic downstream comparison/analysis/report is triggered) -
    # documented in docs/BACKGROUND_JOBS.md, not silently skipped.
    tracker.transition(job_id, JobStage.PREPARING)
    Path(get_settings().artifacts_dir, str(run_id)).mkdir(parents=True, exist_ok=True)
    tracker.transition(job_id, JobStage.COLLECTING_PROVENANCE)

    tracker.transition(job_id, JobStage.EXECUTING)
    run.status = RunStatus.EXECUTING
    db.commit()

    request = build_sandbox_request(experiment, run_id)
    result = (runner or SandboxRunner()).run(request)

    run.exit_code = result.exit_code
    run.finished_at = result.finished_at

    if result.status != SandboxRunStatus.COMPLETED:
        # TIMED_OUT / FAILED / ERROR all mean the run did not complete
        # successfully - RunStatus has no finer-grained distinction.
        run.status = RunStatus.FAILED
        run.error_message = result.stderr[:2000] if result.stderr else f"sandbox status: {result.status.value}"
        tracker.record_failure(job_id, run.error_message)
        db.commit()
        return

    tracker.transition(job_id, JobStage.CAPTURING_ARTIFACTS)
    tracker.transition(job_id, JobStage.COMPARING)
    tracker.transition(job_id, JobStage.ANALYZING)
    tracker.transition(job_id, JobStage.GENERATING_REPORT)
    tracker.transition(job_id, JobStage.COMPLETED)
    run.status = RunStatus.COMPLETED
    db.commit()
