from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel

from app.db.models.enums import DifferenceCategory


class InvestigationCreate(BaseModel):
    comparison_id: uuid.UUID


class InvestigationRead(BaseModel):
    id: uuid.UUID
    comparison_id: uuid.UUID
    base_run_id: uuid.UUID
    compare_run_id: uuid.UUID
    changed_category: DifferenceCategory
    changed_field: str
    original_value: str | None
    target_value: str | None
    evidence_strength: str
    held_constant: list[DifferenceCategory]
    algorithm_version: str
    created_at: datetime
