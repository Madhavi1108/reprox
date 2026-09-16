"""Tests for the DB/Docker-free parts of app.jobs.orchestrator.

`execute_experiment_run` itself needs a real SQLAlchemy Session (Postgres-
specific JSONB/UUID columns rule out a quick sqlite substitute) and a
Docker daemon - neither is available in this environment (see
docs/EXECUTION_SANDBOX.md, docs/BACKGROUND_JOBS.md). Only the pure
`build_sandbox_request` helper is unit-tested here.
"""

from pathlib import Path
from unittest.mock import MagicMock

from app.jobs.orchestrator import build_sandbox_request


def test_build_sandbox_request_derives_paths_from_settings():
    experiment = MagicMock(workload_type="sklearn_tabular", entrypoint_script="train.py")
    run_id = __import__("uuid").uuid4()

    request = build_sandbox_request(experiment, run_id)

    assert request.run_id == run_id
    assert request.entrypoint_script == "train.py"
    assert request.workload_dir == Path("../workloads") / "sklearn_tabular"
    assert request.output_dir == Path("../.data/artifacts") / str(run_id)
    assert request.image == "reprox-sklearn-runner:latest"
    assert request.limits.timeout_seconds == 120
