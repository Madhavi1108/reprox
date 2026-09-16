from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import PageParams
from app.core.errors import NotFoundError
from app.db.models.core import Experiment, Project
from app.db.session import get_db
from app.schemas.common import Page
from app.schemas.experiment import ExperimentCreate, ExperimentRead

router = APIRouter(tags=["experiments"])


def _get_experiment_or_404(db: Session, experiment_id: uuid.UUID) -> Experiment:
    experiment = db.get(Experiment, experiment_id)
    if experiment is None:
        raise NotFoundError(f"experiment {experiment_id} not found")
    return experiment


@router.post("/experiments", response_model=ExperimentRead, status_code=201)
def create_experiment(payload: ExperimentCreate, db: Session = Depends(get_db)) -> Experiment:
    if db.get(Project, payload.project_id) is None:
        raise NotFoundError(f"project {payload.project_id} not found")

    experiment = Experiment(
        id=uuid.uuid4(),
        project_id=payload.project_id,
        name=payload.name,
        description=payload.description,
        workload_type=payload.workload_type,
        entrypoint_script=payload.entrypoint_script,
    )
    db.add(experiment)
    db.commit()
    db.refresh(experiment)
    return experiment


@router.get("/experiments", response_model=Page[ExperimentRead])
def list_experiments(
    db: Session = Depends(get_db), page: PageParams = Depends(), project_id: uuid.UUID | None = None
) -> Page[ExperimentRead]:
    query = db.query(Experiment)
    if project_id is not None:
        query = query.filter(Experiment.project_id == project_id)
    total = query.count()
    items = query.order_by(Experiment.created_at.desc()).offset(page.offset).limit(page.limit).all()
    return Page(items=items, total=total, limit=page.limit, offset=page.offset)


@router.get("/experiments/{experiment_id}", response_model=ExperimentRead)
def get_experiment(experiment_id: uuid.UUID, db: Session = Depends(get_db)) -> Experiment:
    return _get_experiment_or_404(db, experiment_id)
