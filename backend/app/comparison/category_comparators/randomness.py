"""Randomness category comparator (Phase 11).

Fast path is `randomness_fingerprint_hash` equality. On mismatch,
`python_seed`/`numpy_seed`/`other_seeds` are diffed individually, plus
`determinism_classification`/`determinism_intent`. An `other_seeds` value
flipping between bound (an int) and unbound (`None`) is treated as
`Severity.HIGH`, matching `app/provenance/randomness.py`'s own
`_classify_determinism`, which treats "a known stochastic source declared
but not seeded" as decisive for downgrading to NON_DETERMINISTIC.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.comparison.difference import RawDifference, resolve_missing_or_version_mismatch
from app.db.models.enums import ComparisonStatus, Confidence, DifferenceCategory, DifferenceType, Severity
from app.provenance.randomness import RandomnessProvenance

COMPARE_RANDOMNESS_VERSION = "1.0.0"


@dataclass(frozen=True)
class RandomnessComparisonResult:
    status: ComparisonStatus
    differences: list[RawDifference] = field(default_factory=list)


def _diff_seed_field(field_name: str, old: int | None, new: int | None) -> RawDifference | None:
    if old == new:
        return None
    return RawDifference(
        category=DifferenceCategory.RANDOMNESS,
        field=field_name,
        old_value=str(old) if old is not None else None,
        new_value=str(new) if new is not None else None,
        difference_type=DifferenceType.VALUE_CHANGED,
        evidence_source=f"randomness.{field_name}",
        severity=Severity.MEDIUM,
        confidence=Confidence.HIGH,
    )


def _diff_other_seeds(base: RandomnessProvenance, compare: RandomnessProvenance) -> list[RawDifference]:
    differences: list[RawDifference] = []
    base_seeds, compare_seeds = base.other_seeds, compare.other_seeds

    for key in sorted(compare_seeds.keys() - base_seeds.keys()):
        value = compare_seeds[key]
        differences.append(
            RawDifference(
                category=DifferenceCategory.RANDOMNESS,
                field=f"other_seeds.{key}",
                old_value=None,
                new_value=str(value) if value is not None else None,
                difference_type=DifferenceType.ADDED,
                evidence_source="randomness.other_seeds",
                severity=Severity.MEDIUM,
                confidence=Confidence.HIGH,
            )
        )
    for key in sorted(base_seeds.keys() - compare_seeds.keys()):
        value = base_seeds[key]
        differences.append(
            RawDifference(
                category=DifferenceCategory.RANDOMNESS,
                field=f"other_seeds.{key}",
                old_value=str(value) if value is not None else None,
                new_value=None,
                difference_type=DifferenceType.REMOVED,
                evidence_source="randomness.other_seeds",
                severity=Severity.MEDIUM,
                confidence=Confidence.HIGH,
            )
        )
    for key in sorted(base_seeds.keys() & compare_seeds.keys()):
        old_value, new_value = base_seeds[key], compare_seeds[key]
        if old_value == new_value:
            continue
        bound_flipped = (old_value is None) != (new_value is None)
        differences.append(
            RawDifference(
                category=DifferenceCategory.RANDOMNESS,
                field=f"other_seeds.{key}",
                old_value=str(old_value) if old_value is not None else None,
                new_value=str(new_value) if new_value is not None else None,
                difference_type=DifferenceType.VALUE_CHANGED,
                evidence_source="randomness.other_seeds",
                severity=Severity.HIGH if bound_flipped else Severity.MEDIUM,
                confidence=Confidence.HIGH,
            )
        )
    return differences


def compare_randomness(
    base: RandomnessProvenance | None, compare: RandomnessProvenance | None
) -> RandomnessComparisonResult:
    guard = resolve_missing_or_version_mismatch(base, compare, category=DifferenceCategory.RANDOMNESS)
    if guard is not None:
        status, differences = guard
        return RandomnessComparisonResult(status=status, differences=differences)

    if base.randomness_fingerprint_hash == compare.randomness_fingerprint_hash:
        return RandomnessComparisonResult(status=ComparisonStatus.SAME, differences=[])

    differences: list[RawDifference] = []
    python_seed_diff = _diff_seed_field("python_seed", base.python_seed, compare.python_seed)
    if python_seed_diff:
        differences.append(python_seed_diff)
    numpy_seed_diff = _diff_seed_field("numpy_seed", base.numpy_seed, compare.numpy_seed)
    if numpy_seed_diff:
        differences.append(numpy_seed_diff)

    differences += _diff_other_seeds(base, compare)

    if base.determinism_classification != compare.determinism_classification:
        differences.append(
            RawDifference(
                category=DifferenceCategory.RANDOMNESS,
                field="determinism_classification",
                old_value=base.determinism_classification.value,
                new_value=compare.determinism_classification.value,
                difference_type=DifferenceType.VALUE_CHANGED,
                evidence_source="randomness.determinism_classification",
                severity=Severity.HIGH,
                confidence=Confidence.HIGH,
            )
        )

    if base.determinism_intent != compare.determinism_intent:
        differences.append(
            RawDifference(
                category=DifferenceCategory.RANDOMNESS,
                field="determinism_intent",
                old_value=base.determinism_intent.value,
                new_value=compare.determinism_intent.value,
                difference_type=DifferenceType.VALUE_CHANGED,
                evidence_source="randomness.determinism_intent",
                severity=Severity.LOW,
                confidence=Confidence.MEDIUM,
            )
        )

    return RandomnessComparisonResult(status=ComparisonStatus.DIFFERENT, differences=differences)
