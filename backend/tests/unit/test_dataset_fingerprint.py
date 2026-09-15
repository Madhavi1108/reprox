from pathlib import Path

import pytest

from app.provenance.dataset import (
    DatasetFileNotFoundError,
    DatasetParseError,
    capture_dataset_provenance,
)


def _write_csv(path: Path, content: str) -> Path:
    path.write_text(content)
    return path


def test_identical_file_produces_same_hash(tmp_path: Path):
    csv = _write_csv(tmp_path / "a.csv", "x,y,label\n1,2,0\n3,4,1\n5,6,0\n")
    a = capture_dataset_provenance(csv)
    b = capture_dataset_provenance(csv)
    assert a.content_hash == b.content_hash
    assert a.row_count == 3
    assert a.column_count == 3


def test_same_row_count_different_content_is_detected_as_different_dataset(tmp_path: Path):
    original = _write_csv(tmp_path / "orig.csv", "x,y,label\n1,2,0\n3,4,1\n5,6,0\n")
    # same row count, same schema, but labels shuffled -> genuinely a
    # different dataset, must never be reported as "missing" or "same"
    shuffled = _write_csv(tmp_path / "shuffled.csv", "x,y,label\n1,2,1\n3,4,0\n5,6,1\n")

    a = capture_dataset_provenance(original)
    b = capture_dataset_provenance(shuffled)

    assert a.row_count == b.row_count
    assert a.schema == b.schema
    assert a.content_hash != b.content_hash
    # distribution actually differs here (mean of `label` flips)
    label_a = next(c for c in a.column_stats if c.name == "label")
    label_b = next(c for c in b.column_stats if c.name == "label")
    assert label_a.mean != label_b.mean


def test_schema_change_is_detected(tmp_path: Path):
    base = _write_csv(tmp_path / "base.csv", "x,y\n1,2\n3,4\n")
    extra_col = _write_csv(tmp_path / "extra.csv", "x,y,z\n1,2,9\n3,4,9\n")

    a = capture_dataset_provenance(base)
    b = capture_dataset_provenance(extra_col)

    assert a.column_count == 2
    assert b.column_count == 3
    assert a.schema != b.schema
    assert a.content_hash != b.content_hash


def test_missing_dataset_file_raises_not_fabricates(tmp_path: Path):
    with pytest.raises(DatasetFileNotFoundError):
        capture_dataset_provenance(tmp_path / "does_not_exist.csv")


def test_corrupted_dataset_raises_parse_error(tmp_path: Path):
    # Inconsistent column counts across rows is a real-world "corrupted
    # CSV" case that pandas' default C parser rejects.
    bad = _write_csv(tmp_path / "corrupt.csv", "x,y,z\n1,2\n3,4,5,6,7\n")
    with pytest.raises(DatasetParseError):
        capture_dataset_provenance(bad)


def test_duplicate_rows_are_counted(tmp_path: Path):
    csv = _write_csv(tmp_path / "dupes.csv", "x,y\n1,2\n1,2\n3,4\n")
    prov = capture_dataset_provenance(csv)
    assert prov.duplicate_row_count == 1


def test_missing_values_counted_per_column(tmp_path: Path):
    csv = _write_csv(tmp_path / "missing.csv", "x,y\n1,\n,4\n5,6\n")
    prov = capture_dataset_provenance(csv)
    x_stats = next(c for c in prov.column_stats if c.name == "x")
    y_stats = next(c for c in prov.column_stats if c.name == "y")
    assert x_stats.missing_count == 1
    assert y_stats.missing_count == 1


def test_numeric_column_stats_computed(tmp_path: Path):
    csv = _write_csv(tmp_path / "nums.csv", "x\n1\n2\n3\n4\n5\n")
    prov = capture_dataset_provenance(csv)
    x_stats = prov.column_stats[0]
    assert x_stats.mean == 3.0
    assert x_stats.min == 1.0
    assert x_stats.max == 5.0


def test_non_numeric_column_has_no_numeric_stats(tmp_path: Path):
    csv = _write_csv(tmp_path / "cat.csv", "label\nred\ngreen\nblue\n")
    prov = capture_dataset_provenance(csv)
    stats = prov.column_stats[0]
    assert stats.mean is None
    assert stats.distinct_count == 3
