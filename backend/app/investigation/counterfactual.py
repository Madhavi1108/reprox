"""Counterfactual experiment plans and evidence evaluation (Phase 23,
spec section 34).

"Support: What happens if we restore one changed factor? Example:
Original: PyTorch 2.5. Reproduction: PyTorch 2.6. Counterfactual:
PyTorch = 2.5, Everything else = reproduction environment. Execute.
Compare results. If the result moves significantly toward the original,
increase evidence supporting PyTorch as a contributor. Still do NOT
claim causality without sufficient experimental support."

A counterfactual is the mirror image of Phase 22's investigation: an
investigation holds everything at the ORIGINAL and varies one factor
toward the REPRODUCTION; a counterfactual holds everything at the
REPRODUCTION and restores exactly one factor back to the ORIGINAL. Plan
generation reuses Phase 22's `select_contributor` - one selection
algorithm, not two.

"Execute" still isn't automatable here (see app.investigation.planner's
module docstring - the same Phase 17 sandbox limitation applies
identically). But "Compare results" *is* buildable as a pure function
once someone (a human, or a future Phase 17 extension) supplies the
actually-measured counterfactual value - `evaluate_counterfactual_result`
below, reusing Phase 13's existing abs/rel tolerance formula
(`app.comparison.category_comparators.metrics.within_tolerance`) as the
"moved significantly" test rather than inventing a new threshold scheme.
Per the spec's own causality caution, the result vocabulary never reaches
"confirmed" - only SUPPORTS_CONTRIBUTION / DOES_NOT_SUPPORT /
INCONCLUSIVE, matching Phase 14's four-state model's ceiling absent
controlled-rerun execution.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from functools import lru_cache

from app.comparison.category_comparators.metrics import ToleranceConfig, within_tolerance
from app.contributor.ranking import EvidenceStrength, evidence_strength
from app.db.models.enums import DifferenceCategory
from app.investigation.planner import ContributorDifference, held_constant_categories, select_contributor

COUNTERFACTUAL_VERSION = "1.0.0"


class CounterfactualOutcome(str, Enum):
    SUPPORTS_CONTRIBUTION = "SUPPORTS_CONTRIBUTION"
    DOES_NOT_SUPPORT = "DOES_NOT_SUPPORT"
    INCONCLUSIVE = "INCONCLUSIVE"


@dataclass(frozen=True)
class CounterfactualPlan:
    id: uuid.UUID
    comparison_id: uuid.UUID
    base_run_id: uuid.UUID
    compare_run_id: uuid.UUID
    restored_category: DifferenceCategory
    restored_field: str
    restored_value: str | None
    reproduction_value: str | None
    held_at_reproduction: list[DifferenceCategory]
    evidence_strength: EvidenceStrength
    created_at: datetime
    outcome: CounterfactualOutcome | None = None
    algorithm_version: str = COUNTERFACTUAL_VERSION


def generate_counterfactual_plan(
    comparison_id: uuid.UUID,
    base_run_id: uuid.UUID,
    compare_run_id: uuid.UUID,
    differences: list[ContributorDifference],
) -> CounterfactualPlan | None:
    chosen = select_contributor(differences)
    if chosen is None:
        return None

    return CounterfactualPlan(
        id=uuid.uuid4(),
        comparison_id=comparison_id,
        base_run_id=base_run_id,
        compare_run_id=compare_run_id,
        restored_category=chosen.category,
        restored_field=chosen.field,
        restored_value=chosen.old_value,
        reproduction_value=chosen.new_value,
        held_at_reproduction=held_constant_categories(chosen.category),
        evidence_strength=evidence_strength(chosen.severity, chosen.confidence),
        created_at=datetime.now(timezone.utc),
    )


def evaluate_counterfactual_result(
    original_value: float,
    reproduction_value: float,
    counterfactual_value: float,
    tolerance: ToleranceConfig = ToleranceConfig(),
) -> CounterfactualOutcome:
    """"If the result moves significantly toward the original, increase
    evidence supporting [the factor] as a contributor." Reuses Phase 13's
    tolerance formula for "significantly" rather than a new threshold:

    - Counterfactual lands within tolerance of the ORIGINAL -> it moved
      all the way back -> SUPPORTS_CONTRIBUTION.
    - Counterfactual lands within tolerance of the REPRODUCTION -> it
      didn't move at all -> DOES_NOT_SUPPORT.
    - Anything else (moved partway, or moved further away) ->
      INCONCLUSIVE - never claimed as support, per the spec's own
      "do NOT claim causality without sufficient experimental support."
    """
    abs_tol, rel_tol = tolerance.tolerance_for("_counterfactual")

    if within_tolerance(original_value, counterfactual_value, abs_tol, rel_tol):
        return CounterfactualOutcome.SUPPORTS_CONTRIBUTION
    if within_tolerance(reproduction_value, counterfactual_value, abs_tol, rel_tol):
        return CounterfactualOutcome.DOES_NOT_SUPPORT
    return CounterfactualOutcome.INCONCLUSIVE


class CounterfactualStore:
    """In-process store, mirroring Phase 22's `InvestigationStore` - same
    no-new-migration rationale (no reachable Postgres in this environment
    to verify one against)."""

    def __init__(self) -> None:
        self._plans: dict[uuid.UUID, CounterfactualPlan] = {}

    def create(self, plan: CounterfactualPlan) -> CounterfactualPlan:
        self._plans[plan.id] = plan
        return plan

    def get(self, counterfactual_id: uuid.UUID) -> CounterfactualPlan | None:
        return self._plans.get(counterfactual_id)

    def list_all(self) -> list[CounterfactualPlan]:
        return list(self._plans.values())


@lru_cache
def get_counterfactual_store() -> CounterfactualStore:
    return CounterfactualStore()
