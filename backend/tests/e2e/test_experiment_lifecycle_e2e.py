"""Phase 31: the primary story flow, driven entirely through real HTTP
calls against a real (SQLite-backed) database - see conftest.py for why
this is possible now. Project -> experiment -> 2 runs -> compare ->
reproducibility -> report, asserting cross-endpoint consistency of what
was actually persisted, not just 200 OK responses."""

from __future__ import annotations

from tests.e2e.conftest import create_comparison


def test_full_comparison_lifecycle_is_internally_consistent(client):
    state = create_comparison(client)
    comparison = state["comparison"]
    comparison_id = comparison["id"]

    assert comparison["base_run_id"] == state["base_run_id"]
    assert comparison["compare_run_id"] == state["compare_run_id"]
    assert comparison["code_status"] == "DIFFERENT"
    assert len(comparison["differences"]) >= 1

    reproducibility_resp = client.get(f"/api/v1/reproducibility/{comparison_id}")
    assert reproducibility_resp.status_code == 200, reproducibility_resp.text
    reproducibility = reproducibility_resp.json()
    assert reproducibility["comparison_id"] == comparison_id

    report_resp = client.get(f"/api/v1/reports/{comparison_id}")
    assert report_resp.status_code == 200, report_resp.text
    report = report_resp.json()

    assert report["comparison_id"] == comparison_id
    assert report["reproducibility"]["classification"] == reproducibility["classification"]
    assert report["experiment"]["id"] == state["experiment_id"]
    assert report["original_run"]["id"] == state["base_run_id"]
    assert report["reproduction_run"]["id"] == state["compare_run_id"]
    assert len(report["differences"]) == len(comparison["differences"])


def test_reproducibility_404s_for_a_comparison_that_was_never_created(client):
    import uuid

    resp = client.get(f"/api/v1/reproducibility/{uuid.uuid4()}")
    assert resp.status_code == 404


def test_run_creation_persists_and_is_independently_readable(client):
    from tests.e2e.conftest import create_project_and_experiment, create_run

    _, experiment_id = create_project_and_experiment(client)
    run_id = create_run(client, experiment_id)

    get_resp = client.get(f"/api/v1/runs/{run_id}")
    assert get_resp.status_code == 200, get_resp.text
    assert get_resp.json()["experiment_id"] == experiment_id
