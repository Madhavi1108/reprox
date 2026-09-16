from __future__ import annotations

import uuid

from fastapi import APIRouter, BackgroundTasks, Depends
from sqlalchemy.orm import Session

from app.core.errors import NotFoundError
from app.db.models.core import Experiment, ExperimentRun
from app.db.models.enums import JobType, RunStatus
from app.db.session import get_db
from app.jobs.orchestrator import execute_experiment_run, get_job_tracker
from app.jobs.tracker import JobStage, JobTracker
from app.schemas.run import RunCreate, RunCreateResponse, RunRead

router = APIRouter(tags=["runs"])


@router.post("/experiments/{experiment_id}/runs", response_model=RunCreateResponse, status_code=201)
def create_run(
    experiment_id: uuid.UUID,
    payload: RunCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    tracker: JobTracker = Depends(get_job_tracker),
) -> RunCreateResponse:
    experiment = db.get(Experiment, experiment_id)
    if experiment is None:
        raise NotFoundError(f"experiment {experiment_id} not found")
    if payload.parent_run_id is not None and db.get(ExperimentRun, payload.parent_run_id) is None:
        raise NotFoundError(f"parent run {payload.parent_run_id} not found")

    run = ExperimentRun(
        id=uuid.uuid4(),
        experiment_id=experiment_id,
        run_type=payload.run_type,
        parent_run_id=payload.parent_run_id,
        status=RunStatus.CREATED,
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    job_id = tracker.create_job(JobType.RUN_EXPERIMENT, related_run_id=run.id)
    tracker.transition(job_id, JobStage.QUEUED)
    run.status = RunStatus.QUEUED
    db.commit()
    db.refresh(run)

    # Runs in the background after this response returns - see
    # app.jobs.orchestrator's module docstring for the "never actually
    # exercised against a real Docker daemon here" caveat.
    background_tasks.add_task(execute_experiment_run, db, run.id, job_id, tracker)

    return RunCreateResponse(run=run, job_id=job_id)


@router.get("/runs/{run_id}", response_model=RunRead)
def get_run(run_id: uuid.UUID, db: Session = Depends(get_db)) -> ExperimentRun:
    run = db.get(ExperimentRun, run_id)
    if run is None:
        raise NotFoundError(f"run {run_id} not found")
    return run
