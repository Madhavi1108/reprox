from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel

from app.db.models.enums import ReproducibilityClassification


class ReproducibilityRead(BaseModel):
    id: uuid.UUID
    comparison_id: uuid.UUID
    classification: ReproducibilityClassification
    rationale: dict
    algorithm_version: str
    created_at: datetime

    model_config = {"from_attributes": True}
