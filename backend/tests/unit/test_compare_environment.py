from dataclasses import replace

from app.comparison.category_comparators.environment import compare_environment
from app.db.models.enums import ComparisonStatus, DifferenceType
from app.provenance.environment import (
    ENVIRONMENT_FINGERPRINT_VERSION,
    DependencyEntry,
    EnvironmentProvenance,
    capture_environment_provenance,
    compute_environment_fingerprint,
)


def _environment(**overrides) -> EnvironmentProvenance:
    dependencies = overrides.pop("dependencies", [DependencyEntry(package_name="numpy", version="1.26.0")])
    base_kwargs = dict(
        os_name="Linux",
        os_version="5.15",
        architecture="x86_64",
        python_version="3.11.0",
        hostname="host-a",
        cpu_model="Intel",
        cpu_count=8,
        ram_total_mb=16000,
        gpu_present=False,
        gpu_model=None,
        cuda_version=None,
        dependencies=dependencies,
        fingerprint_version=ENVIRONMENT_FINGERPRINT_VERSION,
    )
    base_kwargs.update(overrides)
    env_hash = compute_environment_fingerprint(
        os_name=base_kwargs["os_name"],
        os_version=base_kwargs["os_version"],
        architecture=base_kwargs["architecture"],
        python_version=base_kwargs["python_version"],
        gpu_present=base_kwargs["gpu_present"],
        gpu_model=base_kwargs["gpu_model"],
        cuda_version=base_kwargs["cuda_version"],
        dependencies=base_kwargs["dependencies"],
    )
    return EnvironmentProvenance(**base_kwargs, environment_fingerprint_hash=env_hash)


def test_identical_inputs_are_same():
    result = compare_environment(_environment(), _environment())
    assert result.status == ComparisonStatus.SAME
    assert result.differences == []


def test_hostname_difference_does_not_affect_status():
    base = _environment(hostname="host-a")
    compare = _environment(hostname="host-b")
    result = compare_environment(base, compare)
    assert result.status == ComparisonStatus.SAME
    assert any(d.field == "hostname" for d in result.differences)


def test_os_name_difference_is_different_with_high_severity():
    base = _environment(os_name="Linux")
    compare = _environment(os_name="Windows")
    result = compare_environment(base, compare)
    assert result.status == ComparisonStatus.DIFFERENT
    os_diffs = [d for d in result.differences if d.field == "os_name"]
    assert len(os_diffs) == 1


def test_dependency_version_change_is_flagged():
    base = _environment(dependencies=[DependencyEntry(package_name="numpy", version="1.26.0")])
    compare = _environment(dependencies=[DependencyEntry(package_name="numpy", version="1.27.0")])
    result = compare_environment(base, compare)
    assert result.status == ComparisonStatus.DIFFERENT
    dep_diffs = [d for d in result.differences if d.field == "dependencies.numpy"]
    assert len(dep_diffs) == 1
    assert dep_diffs[0].difference_type == DifferenceType.VALUE_CHANGED


def test_dependency_added_and_removed():
    base = _environment(dependencies=[DependencyEntry(package_name="numpy", version="1.26.0")])
    compare = _environment(
        dependencies=[
            DependencyEntry(package_name="numpy", version="1.26.0"),
            DependencyEntry(package_name="pandas", version="2.0.0"),
        ]
    )
    result = compare_environment(base, compare)
    added = [d for d in result.differences if d.field == "dependencies.pandas"]
    assert len(added) == 1
    assert added[0].difference_type == DifferenceType.ADDED


def test_both_none_is_not_comparable():
    result = compare_environment(None, None)
    assert result.status == ComparisonStatus.NOT_COMPARABLE


def test_one_none_is_unknown():
    result = compare_environment(_environment(), None)
    assert result.status == ComparisonStatus.UNKNOWN


def test_version_mismatch_is_not_comparable():
    result = compare_environment(_environment(), _environment(fingerprint_version="2.0.0"))
    assert result.status == ComparisonStatus.NOT_COMPARABLE


def test_real_capture_identical_process_is_same():
    base = capture_environment_provenance()
    compare = capture_environment_provenance()
    result = compare_environment(base, compare)
    assert result.status == ComparisonStatus.SAME


def test_real_capture_with_mutated_copy_is_different():
    base = capture_environment_provenance()
    compare = replace(base, os_name="SomeOtherOS")
    compare = replace(
        compare,
        environment_fingerprint_hash=compute_environment_fingerprint(
            os_name=compare.os_name,
            os_version=compare.os_version,
            architecture=compare.architecture,
            python_version=compare.python_version,
            gpu_present=compare.gpu_present,
            gpu_model=compare.gpu_model,
            cuda_version=compare.cuda_version,
            dependencies=compare.dependencies,
        ),
    )
    result = compare_environment(base, compare)
    assert result.status == ComparisonStatus.DIFFERENT
