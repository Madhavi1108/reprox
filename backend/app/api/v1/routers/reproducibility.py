from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.errors import NotFoundError
from app.db.models.comparison import ReproducibilityAssessment
from app.db.session import get_db
from app.schemas.reproducibility import ReproducibilityRead

router = APIRouter(tags=["reproducibility"])


@router.get("/reproducibility/{comparison_id}", response_model=ReproducibilityRead)
def get_reproducibility(comparison_id: uuid.UUID, db: Session = Depends(get_db)) -> ReproducibilityRead:
    assessment = db.query(ReproducibilityAssessment).filter_by(comparison_id=comparison_id).one_or_none()
    if assessment is None:
        raise NotFoundError(f"reproducibility assessment for comparison {comparison_id} not found")
    return ReproducibilityRead(
        id=assessment.id,
        comparison_id=assessment.comparison_id,
        classification=assessment.classification,
        rationale=assessment.rationale_json,
        algorithm_version=assessment.algorithm_version,
        created_at=assessment.created_at,
    )
