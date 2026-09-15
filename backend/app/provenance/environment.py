"""Environment provenance capture (spec section 15).

`environment_fingerprint_hash` is computed over the fields that actually
determine execution behavior (OS, architecture, Python version, GPU/CUDA
presence, tracked dependency versions). Descriptive-only metadata
(hostname, CPU model string, RAM size) is captured for display but
deliberately excluded from the hash - two runs on different machines with
an otherwise identical software environment should not appear
"different" just because they have different hostnames.

GPU/CUDA fields are always present in the hash payload (as null when
absent) so that a future run with real GPU/CUDA data changes the hash
without requiring a fingerprint version bump - see docs/FINGERPRINT_ALGORITHM.md.
"""

from __future__ import annotations

import importlib.metadata
import os
import platform
from collections.abc import Sequence
from dataclasses import dataclass, field

from app.provenance.canonicalize import canonical_hash

ENVIRONMENT_FINGERPRINT_VERSION = "1.0.0"

# Packages relevant to the sklearn-tabular MVP workload (spec section 15/16:
# "ML framework, ML framework version"). Not installed => simply omitted,
# never fabricated.
DEFAULT_TRACKED_PACKAGES: tuple[str, ...] = ("numpy", "pandas", "scikit-learn", "scipy")


@dataclass(frozen=True)
class DependencyEntry:
    package_name: str
    version: str


@dataclass(frozen=True)
class EnvironmentProvenance:
    os_name: str
    os_version: str
    architecture: str
    python_version: str
    hostname: str | None
    cpu_model: str | None
    cpu_count: int | None
    ram_total_mb: int | None
    gpu_present: bool
    gpu_model: str | None
    cuda_version: str | None
    dependencies: list[DependencyEntry] = field(default_factory=list)
    environment_fingerprint_hash: str = ""
    fingerprint_version: str = ENVIRONMENT_FINGERPRINT_VERSION


def compute_environment_fingerprint(
    *,
    os_name: str,
    os_version: str,
    architecture: str,
    python_version: str,
    gpu_present: bool,
    gpu_model: str | None,
    cuda_version: str | None,
    dependencies: Sequence[DependencyEntry],
) -> str:
    """Pure hashing function - deliberately excludes hostname/cpu/ram so
    those fields can vary across machines without affecting the hash."""
    payload = {
        "os_name": os_name,
        "os_version": os_version,
        "architecture": architecture,
        "python_version": python_version,
        "gpu_present": gpu_present,
        "gpu_model": gpu_model,
        "cuda_version": cuda_version,
        "dependencies": sorted(
            [{"package": d.package_name, "version": d.version} for d in dependencies],
            key=lambda d: d["package"],
        ),
    }
    return canonical_hash(payload)


def _capture_dependencies(tracked_packages: Sequence[str]) -> list[DependencyEntry]:
    entries: list[DependencyEntry] = []
    for name in tracked_packages:
        try:
            version = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            continue  # not installed - omitted, never fabricated
        entries.append(DependencyEntry(package_name=name, version=version))
    return entries


def _capture_ram_total_mb() -> int | None:
    try:
        import psutil

        return int(psutil.virtual_memory().total / (1024 * 1024))
    except Exception:
        return None  # unavailable on this platform - never guessed


def capture_environment_provenance(
    tracked_packages: Sequence[str] = DEFAULT_TRACKED_PACKAGES,
) -> EnvironmentProvenance:
    """Capture the current process's environment provenance. In the
    execution sandbox (Phase 17) this runs *inside* the container so the
    captured environment reflects what actually executed, not the host's
    guess about it."""
    os_name = platform.system()
    os_version = platform.version()
    architecture = platform.machine()
    python_version = platform.python_version()
    hostname = platform.node() or None
    cpu_model = platform.processor() or None
    cpu_count = os.cpu_count()
    ram_total_mb = _capture_ram_total_mb()

    # No GPU/CUDA capture in the MVP (sklearn CPU-only workload) - fields
    # stay explicitly null rather than guessed, per spec section 18.
    gpu_present = False
    gpu_model: str | None = None
    cuda_version: str | None = None

    dependencies = _capture_dependencies(tracked_packages)

    env_hash = compute_environment_fingerprint(
        os_name=os_name,
        os_version=os_version,
        architecture=architecture,
        python_version=python_version,
        gpu_present=gpu_present,
        gpu_model=gpu_model,
        cuda_version=cuda_version,
        dependencies=dependencies,
    )

    return EnvironmentProvenance(
        os_name=os_name,
        os_version=os_version,
        architecture=architecture,
        python_version=python_version,
        hostname=hostname,
        cpu_model=cpu_model,
        cpu_count=cpu_count,
        ram_total_mb=ram_total_mb,
        gpu_present=gpu_present,
        gpu_model=gpu_model,
        cuda_version=cuda_version,
        dependencies=dependencies,
        environment_fingerprint_hash=env_hash,
    )
