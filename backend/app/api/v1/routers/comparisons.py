from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.comparison.engine import assemble_comparison, compare_experiments
from app.contributor.ranking import rank_contributors
from app.core.errors import NotFoundError, ValidationFailedError
from app.db.models.comparison import ExperimentComparison
from app.db.models.core import ExperimentRun
from app.db.session import get_db
from app.provenance.code import CodeProvenance
from app.provenance.configuration import ConfigurationProvenance
from app.provenance.dataset import DatasetProvenance
from app.provenance.environment import EnvironmentProvenance
from app.provenance.randomness import RandomnessProvenance
from app.reproducibility.classifier import assemble_reproducibility_assessment, classify_reproducibility
from app.schemas.comparison import CompareRequest, ComparisonRead, RunProvenanceIn

router = APIRouter(tags=["comparisons"])

_CATEGORY_DATACLASSES = {
    "code": CodeProvenance,
    "dataset": DatasetProvenance,
    "environment": EnvironmentProvenance,
    "configuration": ConfigurationProvenance,
    "randomness": RandomnessProvenance,
}


def _build_category(side: RunProvenanceIn | None, category: str):
    if side is None:
        return None
    blob = getattr(side, category)
    if blob is None:
        return None
    try:
        return _CATEGORY_DATACLASSES[category](**blob)
    except TypeError as exc:
        raise ValidationFailedError(f"invalid {category!r} provenance payload: {exc}") from exc


@router.post("/runs/{run_id}/compare", response_model=ComparisonRead, status_code=201)
def compare_runs(run_id: uuid.UUID, payload: CompareRequest, db: Session = Depends(get_db)) -> ExperimentComparison:
    if db.get(ExperimentRun, run_id) is None:
        raise NotFoundError(f"run {run_id} not found")
    if db.get(ExperimentRun, payload.compare_run_id) is None:
        raise NotFoundError(f"run {payload.compare_run_id} not found")

    kwargs = {}
    for category in _CATEGORY_DATACLASSES:
        kwargs[f"base_{category}"] = _build_category(payload.base, category)
        kwargs[f"compare_{category}"] = _build_category(payload.compare, category)

    result = compare_experiments(
        **kwargs,
        base_metrics=payload.base.metrics if payload.base else None,
        compare_metrics=payload.compare.metrics if payload.compare else None,
        base_run_id=run_id,
        compare_run_id=payload.compare_run_id,
    )

    classification_result = classify_reproducibility(result)
    ranking = rank_contributors(result, classification_result.classification)

    comparison, differences = assemble_comparison(result, ranking=ranking)
    db.add(comparison)
    db.add_all(differences)
    db.commit()

    assessment = assemble_reproducibility_assessment(comparison.id, classification_result)
    db.add(assessment)
    db.commit()
    db.refresh(comparison)
    return comparison


@router.get("/comparisons/{comparison_id}", response_model=ComparisonRead)
def get_comparison(comparison_id: uuid.UUID, db: Session = Depends(get_db)) -> ExperimentComparison:
    comparison = db.get(ExperimentComparison, comparison_id)
    if comparison is None:
        raise NotFoundError(f"comparison {comparison_id} not found")
    return comparison
