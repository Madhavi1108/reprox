from pathlib import Path

from app.fingerprint.composite import (
    assemble_experiment_fingerprint,
    compute_composite_fingerprint,
)
from app.provenance.code import capture_code_provenance
from app.provenance.configuration import capture_configuration_provenance
from app.provenance.dataset import capture_dataset_provenance
from app.provenance.environment import capture_environment_provenance
from app.provenance.randomness import capture_randomness_provenance


def _all_present_kwargs(**overrides):
    kwargs = dict(
        code_hash="c" * 64,
        dataset_hash="d" * 64,
        environment_hash="e" * 64,
        configuration_hash="f" * 64,
        randomness_hash="r" * 64,
    )
    kwargs.update(overrides)
    return kwargs


def test_deterministic_for_identical_inputs():
    a = compute_composite_fingerprint(**_all_present_kwargs())
    b = compute_composite_fingerprint(**_all_present_kwargs())
    assert a.composite_hash == b.composite_hash


def test_all_categories_present_means_no_missing_components():
    result = compute_composite_fingerprint(**_all_present_kwargs())
    assert result.missing_components == []


def test_missing_category_recorded_explicitly():
    result = compute_composite_fingerprint(**_all_present_kwargs(dataset_hash=None))
    assert result.missing_components == ["dataset_hash"]


def test_missing_category_changes_composite_hash():
    full = compute_composite_fingerprint(**_all_present_kwargs())
    missing_dataset = compute_composite_fingerprint(**_all_present_kwargs(dataset_hash=None))
    assert full.composite_hash != missing_dataset.composite_hash


def test_each_category_change_alters_composite_hash():
    baseline = compute_composite_fingerprint(**_all_present_kwargs())
    for field_name in ["code_hash", "dataset_hash", "environment_hash", "configuration_hash", "randomness_hash"]:
        changed = compute_composite_fingerprint(**_all_present_kwargs(**{field_name: "z" * 64}))
        assert changed.composite_hash != baseline.composite_hash, f"{field_name} change did not alter composite hash"


def test_missing_components_order_is_stable_regardless_of_which_are_missing():
    result = compute_composite_fingerprint(
        **_all_present_kwargs(randomness_hash=None, code_hash=None)
    )
    # Always reported in fixed category order (code before randomness),
    # not insertion/kwargs order.
    assert result.missing_components == ["code_hash", "randomness_hash"]


def test_version_bump_changes_hash_even_with_identical_category_hashes():
    v1 = compute_composite_fingerprint(**_all_present_kwargs(), fingerprint_version="1.0.0")
    v2 = compute_composite_fingerprint(**_all_present_kwargs(), fingerprint_version="2.0.0")
    assert v1.composite_hash != v2.composite_hash
    assert v1.fingerprint_version == "1.0.0"
    assert v2.fingerprint_version == "2.0.0"


def test_all_none_still_produces_a_hash_not_an_error():
    result = compute_composite_fingerprint(
        code_hash=None, dataset_hash=None, environment_hash=None, configuration_hash=None, randomness_hash=None
    )
    assert len(result.composite_hash) == 64
    assert len(result.missing_components) == 5


def test_assemble_from_real_provenance_objects(tmp_path: Path):
    # Real end-to-end assembly using the actual Phase 4-8 capture
    # functions, not synthetic hash strings.
    (tmp_path / "data.csv").write_text("x,y\n1,2\n3,4\n")
    code = capture_code_provenance(tmp_path)
    dataset = capture_dataset_provenance(tmp_path / "data.csv")
    environment = capture_environment_provenance()
    configuration = capture_configuration_provenance({"model": "logreg", "C": 1.0})
    randomness = capture_randomness_provenance(python_seed=42, numpy_seed=42)

    result = assemble_experiment_fingerprint(
        code=code, dataset=dataset, environment=environment, configuration=configuration, randomness=randomness
    )

    assert result.code_hash == code.tree_fingerprint_hash
    assert result.dataset_hash == dataset.content_hash
    assert result.environment_hash == environment.environment_fingerprint_hash
    assert result.configuration_hash == configuration.configuration_fingerprint_hash
    assert result.randomness_hash == randomness.randomness_fingerprint_hash
    assert result.missing_components == []
    assert len(result.composite_hash) == 64


def test_assemble_with_missing_dataset_marks_it_missing(tmp_path: Path):
    (tmp_path / "empty_dir_only.txt").write_text("no dataset here")
    code = capture_code_provenance(tmp_path)
    configuration = capture_configuration_provenance({"model": "logreg"})
    randomness = capture_randomness_provenance(python_seed=1)

    result = assemble_experiment_fingerprint(
        code=code, dataset=None, environment=None, configuration=configuration, randomness=randomness
    )

    assert result.dataset_hash is None
    assert result.environment_hash is None
    assert "dataset_hash" in result.missing_components
    assert "environment_hash" in result.missing_components
