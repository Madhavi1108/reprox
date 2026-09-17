"""Phase 31 E2E fixtures.

Every prior DB-touching test in this repo either mocks the `Session`
entirely or explicitly notes it can't run against real persistence
because there's no reachable Postgres in this environment (see
`tests/unit/test_api_app_wiring.py`'s own docstring, and
`tests/unit/test_job_orchestrator.py`'s "Postgres-specific JSONB/UUID
columns rule out a quick sqlite substitute" note). That blanket
assumption doesn't hold for plain DB-backed flows: `postgresql.UUID` is
SQLAlchemy 2.0's generic cross-dialect `Uuid` type under the hood and
already round-trips through SQLite correctly. The only real
incompatibility is `postgresql.JSONB`, whose DDL compiler has no SQLite
rendering - fixed below with one `@compiles` hook. See
docs/E2E_TESTING.md for the full write-up.

This lets these tests drive the real FastAPI app (`app.main.app`) through
`TestClient`, backed by a real (if SQLite, not Postgres) database, for
genuine multi-endpoint persistence flows - not just wiring/shape checks.
"""

from __future__ import annotations

import uuid
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


@compiles(JSONB, "sqlite")
def _compile_jsonb_for_sqlite(element, compiler, **kw):  # pragma: no cover - DDL compilation hook
    return "JSON"


@pytest.fixture
def client():
    from app.db.base import Base
    from app.db.session import get_db
    from app.main import app

    # StaticPool + a shared in-memory URL keeps every connection in this
    # test on the *same* SQLite database - a plain "sqlite:///:memory:"
    # engine hands out a fresh empty DB per connection, which would make
    # the app and the test see different data.
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    session_local = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

    def _override_get_db():
        db = session_local()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _override_get_db
    try:
        # See create_run()'s docstring: run creation schedules a real
        # BackgroundTasks callback into Phase 17's sandbox, which
        # TestClient executes synchronously - patched to a no-op so these
        # tests stay fast/deterministic/offline; Phase 17/18 already have
        # their own dedicated (mocked-Docker-client) test coverage.
        with patch("app.api.v1.routers.runs.execute_experiment_run"), TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.pop(get_db, None)
        engine.dispose()


def create_project_and_experiment(client: TestClient) -> tuple[str, str]:
    """Shared setup: a real persisted Project + Experiment. Returns
    (project_id, experiment_id) as strings."""
    slug = f"e2e-{uuid.uuid4().hex[:8]}"
    project_resp = client.post("/api/v1/projects", json={"name": "E2E Project", "slug": slug})
    assert project_resp.status_code == 201, project_resp.text
    project_id = project_resp.json()["id"]

    experiment_resp = client.post(
        "/api/v1/experiments",
        json={
            "project_id": project_id,
            "name": "E2E Experiment",
            "workload_type": "sklearn_tabular",
            "entrypoint_script": "train.py",
        },
    )
    assert experiment_resp.status_code == 201, experiment_resp.text
    experiment_id = experiment_resp.json()["id"]
    return project_id, experiment_id


def create_run(client: TestClient, experiment_id: str) -> str:
    """Creates one run and returns its id. Real request creation triggers
    Phase 19's `BackgroundTasks` callback into Phase 17/18's sandbox
    execution path, which degrades gracefully with no Docker daemon
    reachable, is unrelated to what Phase 31 tests, and is slow/network-
    dependent (a real image-pull attempt) - patched to a no-op here so
    these tests stay fast, deterministic, and offline."""
    resp = client.post(f"/api/v1/experiments/{experiment_id}/runs", json={})
    assert resp.status_code == 201, resp.text
    return resp.json()["run"]["id"]


def create_comparison(client: TestClient) -> dict:
    """Full setup through a real, difference-producing comparison: project
    → experiment → 2 runs → compare (with deliberately-differing inline
    code provenance, so Phase 14's contributor ranking has something to
    rank - needed by the investigation/counterfactual/report flows).
    Returns the created project/experiment/run/comparison ids."""
    project_id, experiment_id = create_project_and_experiment(client)
    base_run_id = create_run(client, experiment_id)
    compare_run_id = create_run(client, experiment_id)

    base_code = {
        "vcs_present": True,
        "git_commit_sha": "aaa111",
        "git_branch": "main",
        "is_dirty": False,
        "is_detached_head": False,
        "is_shallow_clone": False,
        "tree_fingerprint_hash": "hash-base",
        "fingerprint_version": "1.0.0",
    }
    compare_code = {**base_code, "git_commit_sha": "bbb222", "tree_fingerprint_hash": "hash-compare"}

    # Metrics deliberately differ too (not just code), so the classifier's
    # outcome axis is DIFFERENT rather than NOT_COMPARABLE - needed to land
    # on NOT_REPRODUCIBLE/PARTIALLY_REPRODUCIBLE, the only classifications
    # Phase 14's rank_contributors() ever flags a potential contributor
    # for (the investigation/counterfactual endpoints 422 otherwise).
    compare_resp = client.post(
        f"/api/v1/runs/{base_run_id}/compare",
        json={
            "compare_run_id": compare_run_id,
            "base": {"code": base_code, "metrics": {"accuracy": 0.9}},
            "compare": {"code": compare_code, "metrics": {"accuracy": 0.5}},
        },
    )
    assert compare_resp.status_code == 201, compare_resp.text
    comparison = compare_resp.json()

    return {
        "project_id": project_id,
        "experiment_id": experiment_id,
        "base_run_id": base_run_id,
        "compare_run_id": compare_run_id,
        "comparison": comparison,
    }
