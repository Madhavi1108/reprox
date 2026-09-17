"""Wiring-level tests for Phase 19's FastAPI app.

No reachable Postgres exists in this environment (same limitation as
Phases 17/18's Docker gap), so these tests can only confirm the app
assembles correctly - every router/schema imports without error and
produces a valid OpenAPI document - and exercise routes that genuinely
don't need a DB. Real request/response behavior against a live database
is unverified here; see docs/API.md.
"""

import uuid

from fastapi.testclient import TestClient

from app.api.deps import get_current_user_id
from app.main import app

client = TestClient(app)

EXPECTED_ROUTES = {
    ("POST", "/api/v1/projects"),
    ("GET", "/api/v1/projects"),
    ("POST", "/api/v1/experiments"),
    ("GET", "/api/v1/experiments"),
    ("GET", "/api/v1/experiments/{experiment_id}"),
    ("POST", "/api/v1/experiments/{experiment_id}/runs"),
    ("GET", "/api/v1/runs/{run_id}"),
    ("POST", "/api/v1/runs/{run_id}/compare"),
    ("GET", "/api/v1/comparisons/{comparison_id}"),
    ("GET", "/api/v1/reproducibility/{comparison_id}"),
    ("GET", "/api/v1/provenance/{run_id}"),
    ("GET", "/api/v1/lineage/{run_id}"),
    ("GET", "/api/v1/jobs"),
    ("GET", "/api/v1/jobs/{job_id}"),
    ("GET", "/api/v1/dashboard"),
    ("POST", "/api/v1/investigations"),
    ("GET", "/api/v1/investigations/{investigation_id}"),
    ("POST", "/api/v1/counterfactuals"),
    ("GET", "/api/v1/counterfactuals/{counterfactual_id}"),
}


def test_health_endpoint_works_without_a_database():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_openapi_schema_generates_successfully():
    response = client.get("/openapi.json")
    assert response.status_code == 200
    spec = response.json()
    assert "paths" in spec
    assert len(spec["paths"]) > 0


def test_all_spec_endpoints_are_registered():
    actual_routes = {
        (method, route.path)
        for route in app.routes
        if hasattr(route, "methods")
        for method in route.methods
        if method != "HEAD"
    }
    missing = EXPECTED_ROUTES - actual_routes
    assert missing == set()


def test_unknown_job_returns_404_without_touching_the_database():
    import uuid

    response = client.get(f"/api/v1/jobs/{uuid.uuid4()}")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_invalid_project_slug_is_rejected_by_schema_validation():
    # FastAPI resolves route dependencies (including get_current_user_id,
    # which needs a real DB) alongside body validation rather than only
    # after it succeeds, so the DB dependency is overridden here purely to
    # isolate the thing this test actually checks: Pydantic schema
    # validation of the request body.
    app.dependency_overrides[get_current_user_id] = lambda: uuid.uuid4()
    try:
        response = client.post("/api/v1/projects", json={"name": "Test", "slug": "Not A Valid Slug!"})
    finally:
        app.dependency_overrides.pop(get_current_user_id, None)
    assert response.status_code == 422
