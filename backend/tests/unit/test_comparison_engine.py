from pathlib import Path

from app.comparison.engine import COMPARISON_ALGORITHM_VERSION, assemble_comparison, compare_experiments
from app.db.models.enums import ComparisonStatus
from app.provenance.code import capture_code_provenance
from app.provenance.configuration import capture_configuration_provenance
from app.provenance.dataset import capture_dataset_provenance
from app.provenance.environment import capture_environment_provenance
from app.provenance.randomness import capture_randomness_provenance


def _capture_all(root: Path, csv_text: str, config: dict, seed: int):
    # Code and dataset are captured from separate subdirectories so that
    # varying the dataset's CSV content in a test doesn't also change the
    # code tree hash (capture_code_provenance walks the whole given root).
    code_dir = root / "code"
    code_dir.mkdir()
    (code_dir / "train.py").write_text("x = 1\n")
    (root / "data.csv").write_text(csv_text)
    return dict(
        code=capture_code_provenance(code_dir),
        dataset=capture_dataset_provenance(root / "data.csv"),
        environment=capture_environment_provenance(),
        configuration=capture_configuration_provenance(config),
        randomness=capture_randomness_provenance(python_seed=seed, numpy_seed=seed),
    )


def test_all_categories_identical_are_same(tmp_path: Path):
    base_dir = tmp_path / "base"
    compare_dir = tmp_path / "compare"
    base_dir.mkdir()
    compare_dir.mkdir()

    base = _capture_all(base_dir, "x,y\n1,2\n3,4\n", {"model": "logreg", "C": 1.0}, seed=42)
    compare = _capture_all(compare_dir, "x,y\n1,2\n3,4\n", {"model": "logreg", "C": 1.0}, seed=42)

    result = compare_experiments(
        base_code=base["code"],
        compare_code=compare["code"],
        base_dataset=base["dataset"],
        compare_dataset=compare["dataset"],
        base_environment=base["environment"],
        compare_environment=compare["environment"],
        base_configuration=base["configuration"],
        compare_configuration=compare["configuration"],
        base_randomness=base["randomness"],
        compare_randomness=compare["randomness"],
    )

    assert result.code_status == ComparisonStatus.SAME
    assert result.dataset_status == ComparisonStatus.SAME
    assert result.environment_status == ComparisonStatus.SAME
    assert result.configuration_status == ComparisonStatus.SAME
    assert result.randomness_status == ComparisonStatus.SAME
    assert result.metrics_status == ComparisonStatus.NOT_COMPARABLE
    assert result.differences == []


def test_only_dataset_differs(tmp_path: Path):
    base_dir = tmp_path / "base"
    compare_dir = tmp_path / "compare"
    base_dir.mkdir()
    compare_dir.mkdir()

    base = _capture_all(base_dir, "x,y\n1,2\n3,4\n", {"model": "logreg", "C": 1.0}, seed=42)
    compare = _capture_all(compare_dir, "x,y\n1,2\n3,5\n", {"model": "logreg", "C": 1.0}, seed=42)

    result = compare_experiments(
        base_code=base["code"],
        compare_code=compare["code"],
        base_dataset=base["dataset"],
        compare_dataset=compare["dataset"],
        base_environment=base["environment"],
        compare_environment=compare["environment"],
        base_configuration=base["configuration"],
        compare_configuration=compare["configuration"],
        base_randomness=base["randomness"],
        compare_randomness=compare["randomness"],
    )

    assert result.dataset_status == ComparisonStatus.DIFFERENT
    assert result.code_status == ComparisonStatus.SAME
    assert result.configuration_status == ComparisonStatus.SAME
    assert result.randomness_status == ComparisonStatus.SAME
    assert all(d.category.value == "DATASET" for d in result.differences)


def test_both_sides_missing_dataset_is_not_comparable(tmp_path: Path):
    base_dir = tmp_path / "base"
    compare_dir = tmp_path / "compare"
    base_dir.mkdir()
    compare_dir.mkdir()

    code_base = capture_code_provenance(base_dir)
    code_compare = capture_code_provenance(compare_dir)
    configuration = capture_configuration_provenance({"model": "logreg"})
    randomness = capture_randomness_provenance(python_seed=1)

    result = compare_experiments(
        base_code=code_base,
        compare_code=code_compare,
        base_dataset=None,
        compare_dataset=None,
        base_environment=None,
        compare_environment=None,
        base_configuration=configuration,
        compare_configuration=configuration,
        base_randomness=randomness,
        compare_randomness=randomness,
    )

    assert result.dataset_status == ComparisonStatus.NOT_COMPARABLE
    assert result.environment_status == ComparisonStatus.NOT_COMPARABLE


def test_assemble_comparison_links_differences_and_defaults_contributor_flag(tmp_path: Path):
    base_dir = tmp_path / "base"
    compare_dir = tmp_path / "compare"
    base_dir.mkdir()
    compare_dir.mkdir()

    base = _capture_all(base_dir, "x,y\n1,2\n3,4\n", {"model": "logreg", "C": 1.0}, seed=42)
    compare = _capture_all(compare_dir, "x,y\n1,2\n3,5\n", {"model": "logreg", "C": 2.0}, seed=42)

    result = compare_experiments(
        base_code=base["code"],
        compare_code=compare["code"],
        base_dataset=base["dataset"],
        compare_dataset=compare["dataset"],
        base_environment=base["environment"],
        compare_environment=compare["environment"],
        base_configuration=base["configuration"],
        compare_configuration=compare["configuration"],
        base_randomness=base["randomness"],
        compare_randomness=compare["randomness"],
    )

    comparison, differences = assemble_comparison(result)

    assert comparison.comparison_algorithm_version == COMPARISON_ALGORITHM_VERSION
    assert len(differences) == len(result.differences)
    assert len(differences) > 0
    for difference in differences:
        assert difference.comparison_id == comparison.id
        assert difference.is_potential_contributor is False


def test_metrics_status_is_not_comparable_when_absent_on_both_sides(tmp_path: Path):
    base_dir = tmp_path / "base"
    compare_dir = tmp_path / "compare"
    base_dir.mkdir()
    compare_dir.mkdir()

    base = _capture_all(base_dir, "x,y\n1,2\n3,4\n", {"model": "logreg"}, seed=1)
    compare = _capture_all(compare_dir, "x,y\n1,2\n3,4\n", {"model": "logreg"}, seed=1)

    result = compare_experiments(
        base_code=base["code"],
        compare_code=compare["code"],
        base_dataset=base["dataset"],
        compare_dataset=compare["dataset"],
        base_environment=base["environment"],
        compare_environment=compare["environment"],
        base_configuration=base["configuration"],
        compare_configuration=compare["configuration"],
        base_randomness=base["randomness"],
        compare_randomness=compare["randomness"],
    )

    assert result.metrics_status == ComparisonStatus.NOT_COMPARABLE


def test_real_metrics_flow_through_to_metrics_status(tmp_path: Path):
    base_dir = tmp_path / "base"
    compare_dir = tmp_path / "compare"
    base_dir.mkdir()
    compare_dir.mkdir()

    base = _capture_all(base_dir, "x,y\n1,2\n3,4\n", {"model": "logreg"}, seed=1)
    compare = _capture_all(compare_dir, "x,y\n1,2\n3,4\n", {"model": "logreg"}, seed=1)

    exact_match = compare_experiments(
        base_code=base["code"],
        compare_code=compare["code"],
        base_dataset=base["dataset"],
        compare_dataset=compare["dataset"],
        base_environment=base["environment"],
        compare_environment=compare["environment"],
        base_configuration=base["configuration"],
        compare_configuration=compare["configuration"],
        base_randomness=base["randomness"],
        compare_randomness=compare["randomness"],
        base_metrics={"accuracy": 0.9427},
        compare_metrics={"accuracy": 0.9427},
    )
    assert exact_match.metrics_status == ComparisonStatus.SAME

    mismatch = compare_experiments(
        base_code=base["code"],
        compare_code=compare["code"],
        base_dataset=base["dataset"],
        compare_dataset=compare["dataset"],
        base_environment=base["environment"],
        compare_environment=compare["environment"],
        base_configuration=base["configuration"],
        compare_configuration=compare["configuration"],
        base_randomness=base["randomness"],
        compare_randomness=compare["randomness"],
        base_metrics={"accuracy": 0.9427},
        compare_metrics={"accuracy": 0.8143},
    )
    assert mismatch.metrics_status == ComparisonStatus.DIFFERENT
    assert any(d.field == "metrics.accuracy" for d in mismatch.differences)
