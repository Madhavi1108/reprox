from pathlib import Path

from app.comparison.category_comparators.code import compare_code
from app.db.models.enums import ComparisonStatus, DifferenceType
from app.provenance.code import CODE_FINGERPRINT_VERSION, CodeFileEntry, CodeProvenance, capture_code_provenance


def _code(**overrides) -> CodeProvenance:
    kwargs = dict(
        vcs_present=True,
        git_commit_sha="a" * 40,
        git_branch="main",
        is_dirty=False,
        is_detached_head=False,
        is_shallow_clone=False,
        tree_fingerprint_hash="t" * 64,
        fingerprint_version=CODE_FINGERPRINT_VERSION,
        files=[CodeFileEntry(relative_path="train.py", size_bytes=10, file_hash="f" * 64, language="python")],
        notes=None,
    )
    kwargs.update(overrides)
    return CodeProvenance(**kwargs)


def test_identical_inputs_are_same():
    result = compare_code(_code(), _code())
    assert result.status == ComparisonStatus.SAME
    assert result.differences == []


def test_changed_tree_hash_and_file_hash_is_different():
    base = _code()
    compare = _code(
        tree_fingerprint_hash="z" * 64,
        files=[CodeFileEntry(relative_path="train.py", size_bytes=10, file_hash="g" * 64, language="python")],
    )
    result = compare_code(base, compare)
    assert result.status == ComparisonStatus.DIFFERENT
    file_diffs = [d for d in result.differences if d.field == "files.train.py"]
    assert len(file_diffs) == 1
    assert file_diffs[0].difference_type == DifferenceType.VALUE_CHANGED
    assert file_diffs[0].old_value == "f" * 64
    assert file_diffs[0].new_value == "g" * 64


def test_added_file_is_flagged_added():
    base = _code()
    compare = _code(
        tree_fingerprint_hash="z" * 64,
        files=[
            CodeFileEntry(relative_path="train.py", size_bytes=10, file_hash="f" * 64, language="python"),
            CodeFileEntry(relative_path="new_file.py", size_bytes=5, file_hash="h" * 64, language="python"),
        ],
    )
    result = compare_code(base, compare)
    added = [d for d in result.differences if d.field == "files.new_file.py"]
    assert len(added) == 1
    assert added[0].difference_type == DifferenceType.ADDED


def test_removed_file_is_flagged_removed():
    base = _code(
        files=[
            CodeFileEntry(relative_path="train.py", size_bytes=10, file_hash="f" * 64, language="python"),
            CodeFileEntry(relative_path="old_file.py", size_bytes=5, file_hash="h" * 64, language="python"),
        ],
    )
    compare = _code(tree_fingerprint_hash="z" * 64)
    result = compare_code(base, compare)
    removed = [d for d in result.differences if d.field == "files.old_file.py"]
    assert len(removed) == 1
    assert removed[0].difference_type == DifferenceType.REMOVED


def test_both_none_is_not_comparable():
    result = compare_code(None, None)
    assert result.status == ComparisonStatus.NOT_COMPARABLE
    assert result.differences == []


def test_one_none_is_unknown():
    result = compare_code(_code(), None)
    assert result.status == ComparisonStatus.UNKNOWN
    assert len(result.differences) == 1
    assert result.differences[0].difference_type == DifferenceType.MISSING_IN_COMPARE


def test_version_mismatch_is_not_comparable():
    result = compare_code(_code(), _code(fingerprint_version="2.0.0"))
    assert result.status == ComparisonStatus.NOT_COMPARABLE


def test_dirty_flag_differs_without_affecting_status():
    base = _code(is_dirty=False)
    compare = _code(is_dirty=True)
    result = compare_code(base, compare)
    assert result.status == ComparisonStatus.SAME
    assert any(d.field == "is_dirty" for d in result.differences)


def test_real_capture_detects_modified_file(tmp_path: Path):
    base_dir = tmp_path / "base"
    compare_dir = tmp_path / "compare"
    base_dir.mkdir()
    compare_dir.mkdir()
    (base_dir / "train.py").write_text("x = 1\n")
    (compare_dir / "train.py").write_text("x = 2\n")

    base = capture_code_provenance(base_dir)
    compare = capture_code_provenance(compare_dir)

    result = compare_code(base, compare)
    assert result.status == ComparisonStatus.DIFFERENT
    assert any(d.field == "files.train.py" for d in result.differences)
