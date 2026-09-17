from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel

from app.db.models.enums import DifferenceCategory


class CounterfactualCreate(BaseModel):
    comparison_id: uuid.UUID
    # The actually-measured metric value from someone having run the
    # suggested restoration (a human, or a future execution mechanism) -
    # REPROX cannot produce this itself. Keyed by metric name to match
    # against the comparison's own METRICS differences.
    counterfactual_metrics: dict[str, float] | None = None


class CounterfactualRead(BaseModel):
    id: uuid.UUID
    comparison_id: uuid.UUID
    base_run_id: uuid.UUID
    compare_run_id: uuid.UUID
    restored_category: DifferenceCategory
    restored_field: str
    restored_value: str | None
    reproduction_value: str | None
    held_at_reproduction: list[DifferenceCategory]
    evidence_strength: str
    outcome: str | None
    algorithm_version: str
    created_at: datetime
