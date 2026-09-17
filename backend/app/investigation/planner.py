"""Controlled investigation plan generation (Phase 22, spec sections 33/35).

"REPROX may generate an investigation: Change ONLY [one factor]. Keep:
Code = same, Dataset = same, Configuration = same, Seed = same,
Hardware = same. Then run the experiment. This allows controlled
evidence collection." (spec section 33) / "Support controlled isolation:
change ONE variable, run, compare." (spec section 35)

This module only builds the **plan** half of that - identifying the
single highest-evidence-strength factor to vary and what to hold
constant, reusing Phase 14's evidence-strength lattice
(`app.contributor.ranking.evidence_strength`) rather than re-deriving it.

It deliberately does **not** claim to execute a controlled rerun: Phase
17's `SandboxRunner` runs a fixed Docker image against a fixed
entrypoint script, with no mechanism to parameterize one specific
dependency version for a single run. Building that would be a separate,
larger infrastructure project, not a natural extension of this phase.
Per spec section 34's own caution ("do NOT claim causality without
sufficient experimental support") and Phase 14's four-state model
(Observed / Potential contributor / Validated contributor / Confirmed
cause), an `InvestigationPlan` is a prerequisite artifact for eventually
reaching "Validated" - never a validation itself, since REPROX has no
controlled-rerun execution capability. See docs/INVESTIGATION_ENGINE.md.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import lru_cache
from typing import Protocol

from app.contributor.ranking import EvidenceStrength, evidence_strength
from app.db.models.enums import Confidence, DifferenceCategory, Severity

INVESTIGATION_PLANNER_VERSION = "1.0.0"

# METRICS is the observed outcome, not a controllable factor - it's never
# a candidate to change, and never appears in `held_constant` either
# (nothing "holds the outcome constant"; you vary a cause and observe it).
_CONTROLLABLE_CATEGORIES = frozenset(
    {
        DifferenceCategory.CODE,
        DifferenceCategory.DATASET,
        DifferenceCategory.ENVIRONMENT,
        DifferenceCategory.CONFIGURATION,
        DifferenceCategory.RANDOMNESS,
    }
)

_SEVERITY_ORDER = {Severity.LOW: 0, Severity.MEDIUM: 1, Severity.HIGH: 2, Severity.CRITICAL: 3}
_CONFIDENCE_ORDER = {Confidence.LOW: 0, Confidence.MEDIUM: 1, Confidence.HIGH: 2}


class ContributorDifference(Protocol):
    """Structural type for whatever difference rows are passed in - either
    Phase 11's `RawDifference` dataclass or a persisted `Difference` ORM
    row both satisfy this, so this module stays decoupled from either."""

    category: DifferenceCategory
    field: str
    old_value: str | None
    new_value: str | None
    severity: Severity
    confidence: Confidence
    is_potential_contributor: bool


@dataclass(frozen=True)
class InvestigationPlan:
    id: uuid.UUID
    comparison_id: uuid.UUID
    base_run_id: uuid.UUID
    compare_run_id: uuid.UUID
    changed_category: DifferenceCategory
    changed_field: str
    original_value: str | None
    target_value: str | None
    evidence_strength: EvidenceStrength
    held_constant: list[DifferenceCategory]
    created_at: datetime
    algorithm_version: str = INVESTIGATION_PLANNER_VERSION


def _tie_break_key(diff: ContributorDifference) -> tuple:
    return (
        -_SEVERITY_ORDER[diff.severity],
        -_CONFIDENCE_ORDER[diff.confidence],
        diff.category.value,
        diff.field,
    )


def generate_investigation_plan(
    comparison_id: uuid.UUID,
    base_run_id: uuid.UUID,
    compare_run_id: uuid.UUID,
    differences: list[ContributorDifference],
) -> InvestigationPlan | None:
    candidates = [
        d for d in differences if d.is_potential_contributor and d.category in _CONTROLLABLE_CATEGORIES
    ]
    if not candidates:
        return None

    chosen = min(candidates, key=_tie_break_key)
    held_constant = sorted(
        (category for category in _CONTROLLABLE_CATEGORIES if category != chosen.category),
        key=lambda c: c.value,
    )

    return InvestigationPlan(
        id=uuid.uuid4(),
        comparison_id=comparison_id,
        base_run_id=base_run_id,
        compare_run_id=compare_run_id,
        changed_category=chosen.category,
        changed_field=chosen.field,
        original_value=chosen.old_value,
        target_value=chosen.new_value,
        evidence_strength=evidence_strength(chosen.severity, chosen.confidence),
        held_constant=held_constant,
        created_at=datetime.now(timezone.utc),
    )


class InvestigationStore:
    """In-process store, mirroring Phase 18's `JobTracker` - no new DB
    table, since no reachable Postgres exists in this environment to
    write and verify a migration against, and persisting a plan that
    can never be executed would add schema for a workflow that's
    intentionally half-built. See docs/INVESTIGATION_ENGINE.md."""

    def __init__(self) -> None:
        self._plans: dict[uuid.UUID, InvestigationPlan] = {}

    def create(self, plan: InvestigationPlan) -> InvestigationPlan:
        self._plans[plan.id] = plan
        return plan

    def get(self, investigation_id: uuid.UUID) -> InvestigationPlan | None:
        return self._plans.get(investigation_id)


@lru_cache
def get_investigation_store() -> InvestigationStore:
    return InvestigationStore()
