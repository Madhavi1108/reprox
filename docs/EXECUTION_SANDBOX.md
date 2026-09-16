# Execution Sandbox

Status: implemented (Phase 17), unit-tested against a **mocked** Docker
client only — see the Verification limitation section below.

Spec section 46 (`REPROX.pdf` page 40, verbatim):

> Experiments are untrusted code. Never execute arbitrary user code directly on the host. Use: Docker or an appropriately isolated execution mechanism. Apply: resource limits, CPU limits, memory limits, execution timeout, filesystem isolation, network restrictions where possible, output limits, process limits. Never expose host secrets.

No numeric thresholds are given — only categories. Implemented in
`app/sandbox/runner.py` (`SANDBOX_RUNNER_VERSION = "1.0.0"`), using
concrete defaults already present in `app/config.py` from an earlier
phase (`sandbox_memory_limit="512m"`, `sandbox_cpu_limit="1"`,
`sandbox_timeout_seconds=120`, `sandbox_image="reprox-sklearn-runner:latest"`).

## Phase 17 vs. Phase 18 boundary

Spec section 45 ("Asynchronous Execution", immediately preceding §46)
defines the job/queue/worker orchestration layer — job ID, status,
progress, retries, cancellation, concurrency limits, and a state machine
(`CREATED → QUEUED → PREPARING → ... → EXECUTING → ...`). That's Phase
18's job (a `Job` table already exists in the schema for it). Phase 17 is
narrower: it's what the Phase 18 worker calls *during* the `EXECUTING`
state — run one container safely, report what happened. This module has
no queue, no retries, no state machine of its own.

## Requirement → mechanism

| Spec requirement | Mechanism |
|---|---|
| CPU limits | `nano_cpus`, derived from `SandboxLimits.cpu_limit` (`"1"` → `1_000_000_000`) |
| Memory limits | `mem_limit=SandboxLimits.memory_limit` (e.g. `"512m"`) |
| Execution timeout | `container.wait(timeout=...)`; if it raises (timeout or otherwise), the container is `kill()`ed and the result reported as `TIMED_OUT` |
| Filesystem isolation | Container root filesystem is `read_only=True`; only two explicit bind mounts exist: `/workload` (host workload dir, **read-only**) and `/output` (host output dir, **read-write**) — no other host path is ever reachable from inside the container |
| Network restrictions | `network_disabled=True` — the default and, in this phase, the only supported setting. ML training workloads don't need network access; this is the conservative default the spec's "where possible" qualifier allows |
| Output limits | `stdout`/`stderr` are each truncated to `_MAX_OUTPUT_CHARS` (1,000,000 characters) before being returned |
| Process limits | `pids_limit` (default 128) |
| Never expose host secrets | `environment={}` is always passed explicitly — the host's `os.environ` is never forwarded into the container, and no secrets file or Docker socket is ever mounted |

## Adjacent security hardening (spec §47)

Two checks run *before* any container is started, rejecting the request
outright via `SandboxConfigError`:

- **Path traversal**: `entrypoint_script` is validated as a `PurePosixPath`
  (the container's OS is always Linux regardless of the host REPROX runs
  on) — an absolute path or any `..` segment is rejected. This also
  checks Windows-style absolute/drive-letter forms so the same guard is
  correct when REPROX itself runs on Windows.
- **Command injection**: the entrypoint is invoked as an explicit
  argument list (`["python", f"/workload/{entrypoint_script}"]`) passed
  directly to the Docker SDK, never through a shell — there is no shell
  interpolation step for an attacker-controlled string to escape.

## Lifecycle guarantee

The container is **always** removed (`container.remove(force=True)`) in
a `finally` block — on success, on a non-zero exit, on timeout, and even
if an unexpected `docker.errors.DockerException` is raised mid-run (which
is itself caught and reported as `SandboxRunStatus.ERROR` rather than
propagating). No code path can leak a running or stopped container.

## Verification limitation

**This module has never been run against a real Docker daemon.** The
development environment that built it has no `docker` CLI or daemon
available (confirmed: `docker` command not found). The `docker` Python
SDK (7.1.0) *is* installed, so `app/sandbox/runner.py` is real,
executable code — but `backend/tests/unit/test_sandbox_runner.py` only
verifies it against a `unittest.mock.MagicMock`-based fake client,
checking that the *correct arguments* (`mem_limit`, `nano_cpus`,
`pids_limit`, `network_disabled`, `read_only`, `environment={}`, the two
volume mounts) are passed to `containers.run`, and that timeout/error/
success paths report the right `SandboxRunStatus` and always clean up.

**What this does *not* verify**: that `docker/sandbox/Dockerfile` builds,
that `workloads/sklearn_tabular/train.py` runs correctly inside it, that
the real Docker daemon actually enforces these limits as configured, or
that no unexpected interaction with a real daemon's API surface exists.
Real end-to-end verification (`docker build`, then a live `SandboxRunner.run()`
against the built image) is necessary before relying on this in
production, and should happen in an environment with Docker available —
CI, or a developer machine.

## Reference image and workload

`docker/sandbox/Dockerfile` — minimal Python 3.11-slim image with
scikit-learn/pandas/numpy, running as a non-root user, matching the
`sandbox_image="reprox-sklearn-runner:latest"` setting.

`workloads/sklearn_tabular/train.py` — the reference workload matching
`Experiment.workload_type="sklearn_tabular"`'s implied contract: reads
`/workload/data.csv` + `/workload/config.json`, writes
`/output/model.joblib` + `/output/metrics.json`. Neither file has been
built or executed in this session, per the limitation above.
