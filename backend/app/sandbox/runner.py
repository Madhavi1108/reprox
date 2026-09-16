"""Experiment execution sandbox (Phase 17, spec section 46).

"Experiments are untrusted code. Never execute arbitrary user code
directly on the host. Use: Docker or an appropriately isolated execution
mechanism. Apply: resource limits, CPU limits, memory limits, execution
timeout, filesystem isolation, network restrictions where possible,
output limits, process limits. Never expose host secrets."

This is the single-run execution primitive the Phase 18 job/worker layer
(spec section 45) invokes for the EXECUTING state - it does not own job
scheduling, retries, or the broader async state machine, only "run this
one container safely and report what happened."

See docs/EXECUTION_SANDBOX.md for the full spec-requirement-to-mechanism
mapping and an explicit note that this module has never been exercised
against a real Docker daemon in this environment - only unit-tested with
a mocked client.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path, PurePosixPath

import docker
from docker.errors import DockerException

from app.config import Settings

SANDBOX_RUNNER_VERSION = "1.0.0"

_MAX_OUTPUT_CHARS = 1_000_000  # spec: "output limits"


class SandboxConfigError(Exception):
    """Raised for an invalid sandbox request, before any container starts."""


class SandboxRunStatus(str, Enum):
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    TIMED_OUT = "TIMED_OUT"
    ERROR = "ERROR"


@dataclass(frozen=True)
class SandboxLimits:
    memory_limit: str
    cpu_limit: str
    timeout_seconds: int
    pids_limit: int = 128
    network_disabled: bool = True

    @staticmethod
    def from_settings(settings: Settings) -> SandboxLimits:
        return SandboxLimits(
            memory_limit=settings.sandbox_memory_limit,
            cpu_limit=settings.sandbox_cpu_limit,
            timeout_seconds=settings.sandbox_timeout_seconds,
        )

    @property
    def nano_cpus(self) -> int:
        return int(float(self.cpu_limit) * 1_000_000_000)


@dataclass(frozen=True)
class SandboxRunRequest:
    run_id: uuid.UUID
    image: str
    workload_dir: Path
    output_dir: Path
    entrypoint_script: str
    limits: SandboxLimits


@dataclass(frozen=True)
class SandboxRunResult:
    status: SandboxRunStatus
    exit_code: int | None
    stdout: str
    stderr: str
    started_at: datetime
    finished_at: datetime
    duration_seconds: float


def _validate_request(request: SandboxRunRequest) -> None:
    # The entrypoint script names a path *inside the container* (mounted at
    # /workload), which is always POSIX - validate with PurePosixPath so
    # this check is correct regardless of the host OS running REPROX.
    script = request.entrypoint_script
    posix_script = PurePosixPath(script)
    if posix_script.is_absolute() or script.startswith("\\") or (len(script) > 1 and script[1] == ":"):
        raise SandboxConfigError(f"entrypoint_script must be relative to the workload dir, got absolute path: {script!r}")
    if ".." in posix_script.parts or ".." in Path(script).parts:
        raise SandboxConfigError(f"entrypoint_script must not contain '..' path segments: {script!r}")


def _truncate(output: bytes) -> str:
    text = output.decode("utf-8", errors="replace")
    if len(text) > _MAX_OUTPUT_CHARS:
        text = text[:_MAX_OUTPUT_CHARS] + "\n... [output truncated]"
    return text


class SandboxRunner:
    """Runs one experiment inside an isolated Docker container.

    `client` is injectable so tests never need a real Docker daemon - it
    defaults to `docker.from_env()`, resolved lazily at run() time (not at
    construction), so simply instantiating a `SandboxRunner` never
    requires Docker to be available.
    """

    def __init__(self, client: docker.DockerClient | None = None) -> None:
        self._client = client

    def _get_client(self) -> docker.DockerClient:
        if self._client is None:
            self._client = docker.from_env()
        return self._client

    def run(self, request: SandboxRunRequest) -> SandboxRunResult:
        _validate_request(request)

        client = self._get_client()
        limits = request.limits
        workload_dir = str(Path(request.workload_dir).resolve())
        output_dir = str(Path(request.output_dir).resolve())

        started_at = datetime.now(timezone.utc)
        container = None
        try:
            container = client.containers.run(
                request.image,
                command=["python", f"/workload/{request.entrypoint_script}"],
                volumes={
                    workload_dir: {"bind": "/workload", "mode": "ro"},
                    output_dir: {"bind": "/output", "mode": "rw"},
                },
                working_dir="/output",
                environment={},  # never pass host secrets/env through
                mem_limit=limits.memory_limit,
                nano_cpus=limits.nano_cpus,
                pids_limit=limits.pids_limit,
                network_disabled=limits.network_disabled,
                read_only=True,
                detach=True,
            )

            try:
                wait_result = container.wait(timeout=limits.timeout_seconds)
                exit_code = wait_result.get("StatusCode") if isinstance(wait_result, dict) else wait_result
                timed_out = False
            except Exception:
                container.kill()
                exit_code = None
                timed_out = True

            stdout = _truncate(container.logs(stdout=True, stderr=False))
            stderr = _truncate(container.logs(stdout=False, stderr=True))

            finished_at = datetime.now(timezone.utc)
            duration_seconds = (finished_at - started_at).total_seconds()

            if timed_out:
                status = SandboxRunStatus.TIMED_OUT
            elif exit_code == 0:
                status = SandboxRunStatus.COMPLETED
            else:
                status = SandboxRunStatus.FAILED

            return SandboxRunResult(
                status=status,
                exit_code=exit_code,
                stdout=stdout,
                stderr=stderr,
                started_at=started_at,
                finished_at=finished_at,
                duration_seconds=duration_seconds,
            )
        except DockerException as exc:
            finished_at = datetime.now(timezone.utc)
            return SandboxRunResult(
                status=SandboxRunStatus.ERROR,
                exit_code=None,
                stdout="",
                stderr=str(exc),
                started_at=started_at,
                finished_at=finished_at,
                duration_seconds=(finished_at - started_at).total_seconds(),
            )
        finally:
            if container is not None:
                try:
                    container.remove(force=True)
                except DockerException:
                    pass
