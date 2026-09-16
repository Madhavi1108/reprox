"""Comparison request/response schemas (Phase 19).

No phase before this one persists captured provenance (CodeSnapshot/
DatasetVersion/Environment/Configuration rows) against a real run - only
the in-memory `capture_*` dataclasses exist, produced wherever the code/
data/environment actually live (a client SDK or the Phase 17 sandbox
runner), never on the API server itself, which has no access to that
filesystem. So `POST /runs/{id}/compare` accepts each side's provenance
as an inline structured payload (matching each Phase 4-8 dataclass's
field names) rather than looking it up from a DB row that doesn't exist
yet - see docs/API.md for the full rationale.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel

from app.db.models.enums import ComparisonStatus, Confidence, DifferenceCategory, DifferenceType, Severity


class RunProvenanceIn(BaseModel):
    code: dict[str, Any] | None = None
    dataset: dict[str, Any] | None = None
    environment: dict[str, Any] | None = None
    configuration: dict[str, Any] | None = None
    randomness: dict[str, Any] | None = None
    metrics: dict[str, float] | None = None


class CompareRequest(BaseModel):
    compare_run_id: uuid.UUID
    base: RunProvenanceIn | None = None
    compare: RunProvenanceIn | None = None


class DifferenceRead(BaseModel):
    id: uuid.UUID
    category: DifferenceCategory
    field: str
    old_value: str | None
    new_value: str | None
    difference_type: DifferenceType
    evidence_source: str
    severity: Severity
    confidence: Confidence
    is_potential_contributor: bool

    model_config = {"from_attributes": True}


class ComparisonRead(BaseModel):
    id: uuid.UUID
    base_run_id: uuid.UUID
    compare_run_id: uuid.UUID
    code_status: ComparisonStatus
    dataset_status: ComparisonStatus
    environment_status: ComparisonStatus
    configuration_status: ComparisonStatus
    randomness_status: ComparisonStatus
    metrics_status: ComparisonStatus
    comparison_algorithm_version: str
    created_at: datetime
    differences: list[DifferenceRead]

    model_config = {"from_attributes": True}
