"""Dataset category comparator (Phase 11).

Fast path is `content_hash` equality. On mismatch, structural fields
(`row_count`, `column_count`, `duplicate_row_count`, `schema`,
`column_stats`) are diffed to explain *why* the datasets differ, matching
`app/provenance/dataset.py`'s own goal of catching "same row count,
different content, same schema, different distribution" instead of
reporting a false match. Comparison is exact equality throughout - no
float tolerance is applied to `column_stats`, since abs/rel tolerance is
explicitly Phase 13's job (metric tolerance), not this phase's.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.comparison.difference import RawDifference, resolve_missing_or_version_mismatch
from app.db.models.enums import ComparisonStatus, Confidence, DifferenceCategory, DifferenceType, Severity
from app.provenance.dataset import ColumnStats, DatasetProvenance

COMPARE_DATASET_VERSION = "1.0.0"

_STAT_FIELDS = ("missing_count", "distinct_count", "mean", "std", "min", "max")


@dataclass(frozen=True)
class DatasetComparisonResult:
    status: ComparisonStatus
    differences: list[RawDifference] = field(default_factory=list)


def _diff_scalar_fields(base: DatasetProvenance, compare: DatasetProvenance) -> list[RawDifference]:
    differences: list[RawDifference] = []
    for name, severity in (
        ("row_count", Severity.MEDIUM),
        ("column_count", Severity.MEDIUM),
        ("duplicate_row_count", Severity.LOW),
    ):
        old, new = getattr(base, name), getattr(compare, name)
        if old != new:
            differences.append(
                RawDifference(
                    category=DifferenceCategory.DATASET,
                    field=name,
                    old_value=str(old),
                    new_value=str(new),
                    difference_type=DifferenceType.VALUE_CHANGED,
                    evidence_source=f"dataset.{name}",
                    severity=severity,
                    confidence=Confidence.HIGH,
                )
            )
    return differences


def _diff_schema(base: DatasetProvenance, compare: DatasetProvenance) -> list[RawDifference]:
    differences: list[RawDifference] = []
    for column in sorted(compare.schema.keys() - base.schema.keys()):
        differences.append(
            RawDifference(
                category=DifferenceCategory.DATASET,
                field=f"schema.{column}",
                old_value=None,
                new_value=compare.schema[column],
                difference_type=DifferenceType.ADDED,
                evidence_source="dataset.schema",
                severity=Severity.HIGH,
                confidence=Confidence.HIGH,
            )
        )
    for column in sorted(base.schema.keys() - compare.schema.keys()):
        differences.append(
            RawDifference(
                category=DifferenceCategory.DATASET,
                field=f"schema.{column}",
                old_value=base.schema[column],
                new_value=None,
                difference_type=DifferenceType.REMOVED,
                evidence_source="dataset.schema",
                severity=Severity.HIGH,
                confidence=Confidence.HIGH,
            )
        )
    for column in sorted(base.schema.keys() & compare.schema.keys()):
        old_dtype, new_dtype = base.schema[column], compare.schema[column]
        if old_dtype != new_dtype:
            differences.append(
                RawDifference(
                    category=DifferenceCategory.DATASET,
                    field=f"schema.{column}",
                    old_value=old_dtype,
                    new_value=new_dtype,
                    difference_type=DifferenceType.TYPE_CHANGED,
                    evidence_source="dataset.schema",
                    severity=Severity.HIGH,
                    confidence=Confidence.HIGH,
                )
            )
    return differences


def _diff_column_stats(base: DatasetProvenance, compare: DatasetProvenance) -> list[RawDifference]:
    base_stats: dict[str, ColumnStats] = {s.name: s for s in base.column_stats}
    compare_stats: dict[str, ColumnStats] = {s.name: s for s in compare.column_stats}
    differences: list[RawDifference] = []

    for column in sorted(base_stats.keys() & compare_stats.keys()):
        base_col, compare_col = base_stats[column], compare_stats[column]
        for stat_field in _STAT_FIELDS:
            old, new = getattr(base_col, stat_field), getattr(compare_col, stat_field)
            if old != new:
                differences.append(
                    RawDifference(
                        category=DifferenceCategory.DATASET,
                        field=f"column_stats.{column}.{stat_field}",
                        old_value=str(old) if old is not None else None,
                        new_value=str(new) if new is not None else None,
                        difference_type=DifferenceType.VALUE_CHANGED,
                        evidence_source="dataset.column_stats",
                        severity=Severity.LOW,
                        confidence=Confidence.MEDIUM,
                    )
                )
    return differences


def compare_dataset(base: DatasetProvenance | None, compare: DatasetProvenance | None) -> DatasetComparisonResult:
    guard = resolve_missing_or_version_mismatch(base, compare, category=DifferenceCategory.DATASET)
    if guard is not None:
        status, differences = guard
        return DatasetComparisonResult(status=status, differences=differences)

    if base.content_hash == compare.content_hash:
        return DatasetComparisonResult(status=ComparisonStatus.SAME, differences=[])

    differences = [
        RawDifference(
            category=DifferenceCategory.DATASET,
            field="content_hash",
            old_value=base.content_hash,
            new_value=compare.content_hash,
            difference_type=DifferenceType.VALUE_CHANGED,
            evidence_source="dataset.content_hash",
            severity=Severity.MEDIUM,
            confidence=Confidence.HIGH,
        )
    ]
    differences += _diff_scalar_fields(base, compare)
    differences += _diff_schema(base, compare)
    differences += _diff_column_stats(base, compare)

    return DatasetComparisonResult(status=ComparisonStatus.DIFFERENT, differences=differences)
