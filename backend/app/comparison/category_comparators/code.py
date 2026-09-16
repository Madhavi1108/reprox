"""Code category comparator (Phase 11).

Fast path is `tree_fingerprint_hash` equality - the same ground-truth
identity `app/provenance/code.py` establishes for "what code was
executed." Git metadata (`vcs_present`, `git_commit_sha`, `git_branch`,
`is_dirty`, `is_detached_head`, `is_shallow_clone`) is informative-only:
it is recorded when it differs but never flips SAME/DIFFERENT, mirroring
that module's own stance that the tree hash - not the commit SHA - is
ground truth.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.comparison.difference import RawDifference, resolve_missing_or_version_mismatch
from app.db.models.enums import ComparisonStatus, Confidence, DifferenceCategory, DifferenceType, Severity
from app.provenance.code import CodeProvenance

COMPARE_CODE_VERSION = "1.0.0"

_INFORMATIONAL_FIELDS = (
    "vcs_present",
    "git_commit_sha",
    "git_branch",
    "is_dirty",
    "is_detached_head",
    "is_shallow_clone",
)


@dataclass(frozen=True)
class CodeComparisonResult:
    status: ComparisonStatus
    differences: list[RawDifference] = field(default_factory=list)


def _diff_informational_fields(base: CodeProvenance, compare: CodeProvenance) -> list[RawDifference]:
    differences: list[RawDifference] = []
    for name in _INFORMATIONAL_FIELDS:
        old = getattr(base, name)
        new = getattr(compare, name)
        if old != new:
            differences.append(
                RawDifference(
                    category=DifferenceCategory.CODE,
                    field=name,
                    old_value=str(old),
                    new_value=str(new),
                    difference_type=DifferenceType.VALUE_CHANGED,
                    evidence_source=f"code.{name}",
                    severity=Severity.LOW,
                    confidence=Confidence.MEDIUM,
                )
            )
    return differences


def _diff_files(base: CodeProvenance, compare: CodeProvenance) -> list[RawDifference]:
    base_files = {f.relative_path: f for f in base.files}
    compare_files = {f.relative_path: f for f in compare.files}
    differences: list[RawDifference] = []

    for path in sorted(compare_files.keys() - base_files.keys()):
        entry = compare_files[path]
        differences.append(
            RawDifference(
                category=DifferenceCategory.CODE,
                field=f"files.{path}",
                old_value=None,
                new_value=entry.file_hash,
                difference_type=DifferenceType.ADDED,
                evidence_source="code.files",
                severity=Severity.MEDIUM,
                confidence=Confidence.HIGH,
            )
        )

    for path in sorted(base_files.keys() - compare_files.keys()):
        entry = base_files[path]
        differences.append(
            RawDifference(
                category=DifferenceCategory.CODE,
                field=f"files.{path}",
                old_value=entry.file_hash,
                new_value=None,
                difference_type=DifferenceType.REMOVED,
                evidence_source="code.files",
                severity=Severity.MEDIUM,
                confidence=Confidence.HIGH,
            )
        )

    for path in sorted(base_files.keys() & compare_files.keys()):
        base_entry, compare_entry = base_files[path], compare_files[path]
        if base_entry.file_hash != compare_entry.file_hash:
            differences.append(
                RawDifference(
                    category=DifferenceCategory.CODE,
                    field=f"files.{path}",
                    old_value=base_entry.file_hash,
                    new_value=compare_entry.file_hash,
                    difference_type=DifferenceType.VALUE_CHANGED,
                    evidence_source="code.files",
                    severity=Severity.MEDIUM,
                    confidence=Confidence.HIGH,
                )
            )

    return differences


def compare_code(base: CodeProvenance | None, compare: CodeProvenance | None) -> CodeComparisonResult:
    guard = resolve_missing_or_version_mismatch(base, compare, category=DifferenceCategory.CODE)
    if guard is not None:
        status, differences = guard
        return CodeComparisonResult(status=status, differences=differences)

    if base.tree_fingerprint_hash is None and compare.tree_fingerprint_hash is None:
        return CodeComparisonResult(status=ComparisonStatus.NOT_COMPARABLE, differences=[])

    if base.tree_fingerprint_hash is None or compare.tree_fingerprint_hash is None:
        difference_type = (
            DifferenceType.MISSING_IN_BASE if base.tree_fingerprint_hash is None else DifferenceType.MISSING_IN_COMPARE
        )
        return CodeComparisonResult(
            status=ComparisonStatus.UNKNOWN,
            differences=[
                RawDifference(
                    category=DifferenceCategory.CODE,
                    field="tree_fingerprint_hash",
                    old_value=base.tree_fingerprint_hash,
                    new_value=compare.tree_fingerprint_hash,
                    difference_type=difference_type,
                    evidence_source="code.tree_fingerprint_hash",
                    severity=Severity.MEDIUM,
                    confidence=Confidence.HIGH,
                )
            ],
        )

    informational = _diff_informational_fields(base, compare)

    if base.tree_fingerprint_hash == compare.tree_fingerprint_hash:
        return CodeComparisonResult(status=ComparisonStatus.SAME, differences=informational)

    differences = _diff_files(base, compare) + informational
    return CodeComparisonResult(status=ComparisonStatus.DIFFERENT, differences=differences)
