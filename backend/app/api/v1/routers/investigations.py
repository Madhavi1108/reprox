"""POST /investigations, GET /investigations/{id} (Phase 22).

Reads/writes the in-process `InvestigationStore` (Phase 22), not a DB
table - see docs/INVESTIGATION_ENGINE.md for why no migration was added
in this environment (same rationale as Phase 18's job tracker).
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.errors import NotFoundError, ValidationFailedError
from app.db.models.comparison import ExperimentComparison
from app.db.session import get_db
from app.investigation.planner import InvestigationStore, generate_investigation_plan, get_investigation_store
from app.schemas.investigation import InvestigationCreate, InvestigationRead

router = APIRouter(tags=["investigations"])


def _to_read(plan) -> InvestigationRead:
    return InvestigationRead(
        id=plan.id,
        comparison_id=plan.comparison_id,
        base_run_id=plan.base_run_id,
        compare_run_id=plan.compare_run_id,
        changed_category=plan.changed_category,
        changed_field=plan.changed_field,
        original_value=plan.original_value,
        target_value=plan.target_value,
        evidence_strength=plan.evidence_strength.value,
        held_constant=plan.held_constant,
        algorithm_version=plan.algorithm_version,
        created_at=plan.created_at,
    )


@router.post("/investigations", response_model=InvestigationRead, status_code=201)
def create_investigation(
    payload: InvestigationCreate,
    db: Session = Depends(get_db),
    store: InvestigationStore = Depends(get_investigation_store),
) -> InvestigationRead:
    comparison = db.get(ExperimentComparison, payload.comparison_id)
    if comparison is None:
        raise NotFoundError(f"comparison {payload.comparison_id} not found")

    plan = generate_investigation_plan(
        comparison.id, comparison.base_run_id, comparison.compare_run_id, comparison.differences
    )
    if plan is None:
        raise ValidationFailedError(
            f"comparison {payload.comparison_id} has no potential contributors to investigate"
        )

    store.create(plan)
    return _to_read(plan)


@router.get("/investigations/{investigation_id}", response_model=InvestigationRead)
def get_investigation(
    investigation_id: uuid.UUID, store: InvestigationStore = Depends(get_investigation_store)
) -> InvestigationRead:
    plan = store.get(investigation_id)
    if plan is None:
        raise NotFoundError(f"investigation {investigation_id} not found")
    return _to_read(plan)
