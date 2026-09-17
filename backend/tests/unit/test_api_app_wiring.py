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
    ("POST", "/api/v1/comparisons/{comparison_id}/explain"),
    ("GET", "/api/v1/search"),
    ("GET", "/api/v1/reports/{comparison_id}"),
    ("GET", "/api/v1/exports/excel"),
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
    # Walking `app.routes` directly is fragile across FastAPI/Starlette
    # versions: as of fastapi 0.141/starlette 1.6 (this project only pins
    # fastapi>=0.115, so a much newer version resolves), `include_router`
    # stores each sub-router as an opaque, lazily-expanded `_IncludedRouter`
    # wrapper rather than flattening its routes into `app.routes` up front
    # - so `hasattr(route, "methods")` silently filters out every route
    # from every included router, leaving only the directly-declared ones
    # (/health, /health/db, /docs, /redoc, /openapi.json). This produced a
    # false-negative "missing 23 routes" failure even though the app
    # genuinely serves all of them (verified live: a real running server
    # returns 200 for GET /api/v1/projects and lists all 23 paths in its
    # own /openapi.json). The app's generated OpenAPI schema is the
    # correct, version-stable source of truth for "what's actually
    # registered and reachable" - it's the same document a real client
    # would introspect, and what /openapi.json serves over the wire.
    spec = app.openapi()
    actual_routes = {
        (method.upper(), path) for path, methods in spec["paths"].items() for method in methods if method != "head"
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


def test_oversized_project_description_is_rejected_by_schema_validation():
    # Found during a live-infra hardening pass (real Postgres + a real
    # running server): unlike every other string field on this schema
    # (name/slug both have max_length), `description` had none, so a
    # 20MB request body was silently accepted and persisted - a real
    # unbounded-input gap, not a hypothetical one. Fixed in
    # app/schemas/project.py; this pins the fix.
    app.dependency_overrides[get_current_user_id] = lambda: uuid.uuid4()
    try:
        response = client.post(
            "/api/v1/projects",
            json={"name": "Test", "slug": "valid-slug", "description": "x" * 5001},
        )
    finally:
        app.dependency_overrides.pop(get_current_user_id, None)
    assert response.status_code == 422


def test_oversized_experiment_description_is_rejected_by_schema_validation():
    response = client.post(
        "/api/v1/experiments",
        json={
            "project_id": str(uuid.uuid4()),
            "name": "Test",
            "entrypoint_script": "train.py",
            "description": "x" * 5001,
        },
    )
    assert response.status_code == 422


def test_search_without_query_param_is_rejected_by_schema_validation():
    # Missing `q` fails FastAPI's own Query(..., min_length=1) validation
    # before the endpoint body (and its DB queries) ever runs, so this is
    # safely testable without a reachable Postgres, same reasoning as
    # test_invalid_project_slug_is_rejected_by_schema_validation above.
    response = client.get("/api/v1/search")
    assert response.status_code == 422
