"""POST /counterfactuals, GET /counterfactuals/{id} (Phase 23).

Reads/writes the in-process `CounterfactualStore`, not a DB table - same
rationale as Phase 22's `InvestigationStore` (docs/INVESTIGATION_ENGINE.md,
docs/COUNTERFACTUAL_EXPERIMENTS.md).
"""

from __future__ import annotations

import uuid
from dataclasses import replace

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.errors import NotFoundError, ValidationFailedError
from app.db.models.comparison import ExperimentComparison
from app.db.session import get_db
from app.investigation.counterfactual import (
    CounterfactualStore,
    evaluate_counterfactual_result,
    generate_counterfactual_plan,
    get_counterfactual_store,
)
from app.schemas.counterfactual import CounterfactualCreate, CounterfactualRead

router = APIRouter(tags=["counterfactuals"])


def _to_read(plan) -> CounterfactualRead:
    return CounterfactualRead(
        id=plan.id,
        comparison_id=plan.comparison_id,
        base_run_id=plan.base_run_id,
        compare_run_id=plan.compare_run_id,
        restored_category=plan.restored_category,
        restored_field=plan.restored_field,
        restored_value=plan.restored_value,
        reproduction_value=plan.reproduction_value,
        held_at_reproduction=plan.held_at_reproduction,
        evidence_strength=plan.evidence_strength.value,
        outcome=plan.outcome.value if plan.outcome else None,
        algorithm_version=plan.algorithm_version,
        created_at=plan.created_at,
    )


def _find_metric_evaluation(comparison: ExperimentComparison, counterfactual_metrics: dict[str, float]):
    """Looks up a METRICS difference matching one of the supplied
    counterfactual metric names, giving us (original, reproduction) to
    compare the counterfactual's measured value against."""
    for diff in comparison.differences:
        if diff.category.value != "METRICS":
            continue
        name = diff.field.removeprefix("metrics.")
        if name in counterfactual_metrics and diff.old_value is not None and diff.new_value is not None:
            return float(diff.old_value), float(diff.new_value), counterfactual_metrics[name]
    return None


@router.post("/counterfactuals", response_model=CounterfactualRead, status_code=201)
def create_counterfactual(
    payload: CounterfactualCreate,
    db: Session = Depends(get_db),
    store: CounterfactualStore = Depends(get_counterfactual_store),
) -> CounterfactualRead:
    comparison = db.get(ExperimentComparison, payload.comparison_id)
    if comparison is None:
        raise NotFoundError(f"comparison {payload.comparison_id} not found")

    plan = generate_counterfactual_plan(
        comparison.id, comparison.base_run_id, comparison.compare_run_id, comparison.differences
    )
    if plan is None:
        raise ValidationFailedError(
            f"comparison {payload.comparison_id} has no potential contributors to build a counterfactual around"
        )

    if payload.counterfactual_metrics:
        match = _find_metric_evaluation(comparison, payload.counterfactual_metrics)
        if match is not None:
            original, reproduction, counterfactual_value = match
            outcome = evaluate_counterfactual_result(original, reproduction, counterfactual_value)
            plan = replace(plan, outcome=outcome)

    store.create(plan)
    return _to_read(plan)


@router.get("/counterfactuals/{counterfactual_id}", response_model=CounterfactualRead)
def get_counterfactual(
    counterfactual_id: uuid.UUID, store: CounterfactualStore = Depends(get_counterfactual_store)
) -> CounterfactualRead:
    plan = store.get(counterfactual_id)
    if plan is None:
        raise NotFoundError(f"counterfactual {counterfactual_id} not found")
    return _to_read(plan)
