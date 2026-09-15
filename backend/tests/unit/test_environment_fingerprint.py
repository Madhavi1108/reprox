import platform

from app.provenance.environment import (
    DependencyEntry,
    capture_environment_provenance,
    compute_environment_fingerprint,
)


def _base_kwargs(**overrides):
    kwargs = dict(
        os_name="Linux",
        os_version="5.15.0",
        architecture="x86_64",
        python_version="3.12.10",
        gpu_present=False,
        gpu_model=None,
        cuda_version=None,
        dependencies=[DependencyEntry("numpy", "1.26.4"), DependencyEntry("pandas", "2.2.2")],
    )
    kwargs.update(overrides)
    return kwargs


def test_deterministic_for_identical_inputs():
    a = compute_environment_fingerprint(**_base_kwargs())
    b = compute_environment_fingerprint(**_base_kwargs())
    assert a == b


def test_dependency_version_change_alters_hash():
    a = compute_environment_fingerprint(**_base_kwargs())
    b = compute_environment_fingerprint(
        **_base_kwargs(dependencies=[DependencyEntry("numpy", "1.26.5"), DependencyEntry("pandas", "2.2.2")])
    )
    assert a != b


def test_dependency_order_does_not_affect_hash():
    a = compute_environment_fingerprint(
        **_base_kwargs(dependencies=[DependencyEntry("numpy", "1.26.4"), DependencyEntry("pandas", "2.2.2")])
    )
    b = compute_environment_fingerprint(
        **_base_kwargs(dependencies=[DependencyEntry("pandas", "2.2.2"), DependencyEntry("numpy", "1.26.4")])
    )
    assert a == b


def test_gpu_presence_toggle_alters_hash():
    a = compute_environment_fingerprint(**_base_kwargs(gpu_present=False))
    b = compute_environment_fingerprint(**_base_kwargs(gpu_present=True, gpu_model="RTX 4060", cuda_version="12.1"))
    assert a != b


def test_python_version_change_alters_hash():
    a = compute_environment_fingerprint(**_base_kwargs(python_version="3.12.10"))
    b = compute_environment_fingerprint(**_base_kwargs(python_version="3.11.9"))
    assert a != b


def test_hostname_cpu_ram_are_not_part_of_the_hash_function_signature():
    # compute_environment_fingerprint has no hostname/cpu/ram parameters
    # at all - this is the structural guarantee that descriptive-only
    # metadata can never leak into the fingerprint.
    import inspect

    sig = inspect.signature(compute_environment_fingerprint)
    assert "hostname" not in sig.parameters
    assert "cpu_model" not in sig.parameters
    assert "ram_total_mb" not in sig.parameters


def test_capture_environment_provenance_reflects_real_host():
    prov = capture_environment_provenance()
    assert prov.python_version == platform.python_version()
    assert prov.gpu_present is False
    assert prov.gpu_model is None
    assert prov.cuda_version is None
    assert len(prov.environment_fingerprint_hash) == 64


def test_capture_environment_provenance_is_deterministic_across_calls():
    a = capture_environment_provenance()
    b = capture_environment_provenance()
    assert a.environment_fingerprint_hash == b.environment_fingerprint_hash


def test_untracked_or_missing_package_is_omitted_not_fabricated():
    prov = capture_environment_provenance(tracked_packages=["numpy", "this-package-does-not-exist-xyz"])
    names = [d.package_name for d in prov.dependencies]
    assert "numpy" in names
    assert "this-package-does-not-exist-xyz" not in names
