"""POST /comparisons/{id}/explain (Phase 24).

Not in spec §72's literal minimum endpoint list, but required by
acceptance checklist item 27 ("AI explanations are evidence-backed") -
the same "necessary addition" situation as Phase 19's /dashboard.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.ai.explainer import explain_comparison
from app.ai.provider import get_ai_provider
from app.config import get_settings
from app.core.errors import NotFoundError
from app.db.models.comparison import ExperimentComparison, ReproducibilityAssessment
from app.db.session import get_db
from app.schemas.explanation import ExplanationRead

router = APIRouter(tags=["explanations"])


@router.post("/comparisons/{comparison_id}/explain", response_model=ExplanationRead)
def explain(comparison_id: uuid.UUID, db: Session = Depends(get_db)) -> ExplanationRead:
    comparison = db.get(ExperimentComparison, comparison_id)
    if comparison is None:
        raise NotFoundError(f"comparison {comparison_id} not found")

    reproducibility = db.query(ReproducibilityAssessment).filter_by(comparison_id=comparison_id).one_or_none()
    provider = get_ai_provider(get_settings())

    result = explain_comparison(comparison, reproducibility, provider)

    return ExplanationRead(
        status=result.status.value,
        text=result.text,
        evidence_ids=result.evidence_ids,
        provider_name=result.provider_name,
    )
