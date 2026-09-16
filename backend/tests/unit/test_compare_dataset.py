from pathlib import Path

from app.comparison.category_comparators.dataset import compare_dataset
from app.db.models.enums import ComparisonStatus, DifferenceType
from app.provenance.dataset import (
    DATASET_FINGERPRINT_VERSION,
    ColumnStats,
    DatasetProvenance,
    capture_dataset_provenance,
)


def _stats(**overrides) -> ColumnStats:
    kwargs = dict(name="x", dtype="int64", missing_count=0, distinct_count=5, mean=2.0, std=1.0, min=0.0, max=4.0)
    kwargs.update(overrides)
    return ColumnStats(**kwargs)


def _dataset(**overrides) -> DatasetProvenance:
    kwargs = dict(
        content_hash="c" * 64,
        file_size_bytes=100,
        row_count=10,
        column_count=2,
        schema={"x": "int64", "y": "int64"},
        column_stats=[_stats(name="x"), _stats(name="y")],
        duplicate_row_count=0,
        fingerprint_version=DATASET_FINGERPRINT_VERSION,
    )
    kwargs.update(overrides)
    return DatasetProvenance(**kwargs)


def test_identical_content_hash_is_same():
    result = compare_dataset(_dataset(), _dataset())
    assert result.status == ComparisonStatus.SAME
    assert result.differences == []


def test_same_row_count_different_content_and_stats_is_different():
    base = _dataset()
    compare = _dataset(content_hash="d" * 64, column_stats=[_stats(name="x", mean=3.5), _stats(name="y")])
    result = compare_dataset(base, compare)
    assert result.status == ComparisonStatus.DIFFERENT
    mean_diffs = [d for d in result.differences if d.field == "column_stats.x.mean"]
    assert len(mean_diffs) == 1
    assert mean_diffs[0].old_value == "2.0"
    assert mean_diffs[0].new_value == "3.5"


def test_added_schema_column_is_flagged_high_severity():
    base = _dataset()
    compare = _dataset(
        content_hash="d" * 64,
        column_count=3,
        schema={"x": "int64", "y": "int64", "z": "float64"},
        column_stats=[_stats(name="x"), _stats(name="y"), _stats(name="z")],
    )
    result = compare_dataset(base, compare)
    added = [d for d in result.differences if d.field == "schema.z"]
    assert len(added) == 1
    assert added[0].difference_type == DifferenceType.ADDED


def test_dtype_change_is_type_changed():
    base = _dataset()
    compare = _dataset(content_hash="d" * 64, schema={"x": "float64", "y": "int64"})
    result = compare_dataset(base, compare)
    type_changed = [d for d in result.differences if d.field == "schema.x"]
    assert len(type_changed) == 1
    assert type_changed[0].difference_type == DifferenceType.TYPE_CHANGED


def test_duplicate_row_count_difference_recorded():
    base = _dataset()
    compare = _dataset(content_hash="d" * 64, duplicate_row_count=3)
    result = compare_dataset(base, compare)
    assert any(d.field == "duplicate_row_count" for d in result.differences)


def test_both_none_is_not_comparable():
    result = compare_dataset(None, None)
    assert result.status == ComparisonStatus.NOT_COMPARABLE


def test_one_none_is_unknown():
    result = compare_dataset(_dataset(), None)
    assert result.status == ComparisonStatus.UNKNOWN


def test_version_mismatch_is_not_comparable():
    result = compare_dataset(_dataset(), _dataset(fingerprint_version="2.0.0"))
    assert result.status == ComparisonStatus.NOT_COMPARABLE


def test_real_capture_detects_changed_cell(tmp_path: Path):
    base_csv = tmp_path / "base.csv"
    compare_csv = tmp_path / "compare.csv"
    base_csv.write_text("x,y\n1,2\n3,4\n")
    compare_csv.write_text("x,y\n1,2\n3,5\n")

    base = capture_dataset_provenance(base_csv)
    compare = capture_dataset_provenance(compare_csv)

    result = compare_dataset(base, compare)
    assert result.status == ComparisonStatus.DIFFERENT
    assert any(d.field == "content_hash" for d in result.differences)
