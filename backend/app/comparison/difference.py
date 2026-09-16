"""Shared comparison primitives (spec section 22-23 / Phase 11).

`RawDifference` is a plain, DB-free intermediate representation of a
single field-level difference - comparators return these, never ORM
`Difference` rows directly, so every comparator stays a pure function
testable with bare `assert`s (no session, no `comparison_id` FK, which
doesn't exist until `engine.assemble_comparison` builds the parent row).

`resolve_missing_or_version_mismatch` is the one guard clause shared by
every per-category comparator, encoding two decisions that must stay
consistent across all five categories:

  - both sides `None` -> NOT_COMPARABLE: no evidence exists on either run,
    there is nothing to say beyond "we don't know."
  - exactly one side `None` -> UNKNOWN (not NOT_COMPARABLE): the run that
    *does* have the category is still informative, so this is weaker than
    "can't compare at all" - and it comes with an explicit
    MISSING_IN_BASE/MISSING_IN_COMPARE difference rather than silence.
  - both present but `fingerprint_version` differs -> NOT_COMPARABLE: a
    version mismatch is itself a signal the comparison engine must not
    paper over (see docs/FINGERPRINT_ALGORITHM.md and
    docs/COMPARISON_ENGINE.md).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.db.models.enums import (
    Confidence,
    ComparisonStatus,
    DifferenceCategory,
    DifferenceType,
    Severity,
)


@dataclass(frozen=True)
class RawDifference:
    category: DifferenceCategory
    field: str
    old_value: str | None
    new_value: str | None
    difference_type: DifferenceType
    evidence_source: str
    severity: Severity = Severity.LOW
    confidence: Confidence = Confidence.MEDIUM


def resolve_missing_or_version_mismatch(
    base: Any | None,
    compare: Any | None,
    *,
    category: DifferenceCategory,
    version_field: str = "fingerprint_version",
) -> tuple[ComparisonStatus, list[RawDifference]] | None:
    """Returns a terminal `(status, differences)` pair if `base`/`compare`
    can't be meaningfully compared at all, else `None` to signal "both are
    present with matching versions - proceed with real comparison logic"."""
    category_name = category.value.lower()

    if base is None and compare is None:
        return ComparisonStatus.NOT_COMPARABLE, []

    if base is None or compare is None:
        difference_type = DifferenceType.MISSING_IN_BASE if base is None else DifferenceType.MISSING_IN_COMPARE
        return ComparisonStatus.UNKNOWN, [
            RawDifference(
                category=category,
                field=category_name,
                old_value=None if base is None else "present",
                new_value=None if compare is None else "present",
                difference_type=difference_type,
                evidence_source=f"{category_name}.presence",
                severity=Severity.MEDIUM,
                confidence=Confidence.HIGH,
            )
        ]

    base_version = getattr(base, version_field, None)
    compare_version = getattr(compare, version_field, None)
    if base_version != compare_version:
        return ComparisonStatus.NOT_COMPARABLE, [
            RawDifference(
                category=category,
                field=version_field,
                old_value=str(base_version) if base_version is not None else None,
                new_value=str(compare_version) if compare_version is not None else None,
                difference_type=DifferenceType.VALUE_CHANGED,
                evidence_source=f"{category_name}.{version_field}",
                severity=Severity.LOW,
                confidence=Confidence.HIGH,
            )
        ]

    return None
