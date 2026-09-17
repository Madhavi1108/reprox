from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel


class ExperimentSummary(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    workload_type: str


class RunSummary(BaseModel):
    id: uuid.UUID
    run_type: str
    status: str
    exit_code: int | None
    started_at: datetime | None
    finished_at: datetime | None


class CategoryProvenanceRead(BaseModel):
    category: str
    availability: str
    status: str | None = None
    reason: str | None = None


class MetricComparisonRead(BaseModel):
    status: str
    reason: str | None = None


class DifferenceRead(BaseModel):
    id: str
    category: str
    field: str
    old_value: str | None
    new_value: str | None
    difference_type: str
    severity: str
    confidence: str
    evidence_source: str
    is_potential_contributor: bool


class ContributorRead(BaseModel):
    difference_id: str
    category: str
    field: str
    evidence_strength: str


class ReproducibilitySummaryRead(BaseModel):
    available: bool
    classification: str | None = None
    rationale: dict | None = None


class InvestigationSummaryRead(BaseModel):
    available: bool
    investigation_id: str | None = None
    changed_category: str | None = None
    changed_field: str | None = None
    evidence_strength: str | None = None
    reason: str | None = None


class CounterfactualSummaryRead(BaseModel):
    available: bool
    counterfactual_id: str | None = None
    restored_category: str | None = None
    restored_field: str | None = None
    outcome: str | None = None
    reason: str | None = None


class ReportRead(BaseModel):
    report_version: str
    comparison_id: uuid.UUID
    experiment: ExperimentSummary
    original_run: RunSummary
    reproduction_run: RunSummary
    provenance: list[CategoryProvenanceRead]
    metric_comparison: MetricComparisonRead
    differences: list[DifferenceRead]
    reproducibility: ReproducibilitySummaryRead
    potential_contributors: list[ContributorRead]
    investigation: InvestigationSummaryRead
    counterfactual: CounterfactualSummaryRead
    limitations: list[str]
    evidence_references: list[str]
    generated_at: datetime
