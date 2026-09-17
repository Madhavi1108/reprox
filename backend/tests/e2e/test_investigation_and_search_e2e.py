"""Phase 31: investigation/counterfactual flows (Phase 22/23, in-process
stores backing real DB-derived comparisons), plus search/dashboard
aggregation flows - all against real persisted data."""

from __future__ import annotations

from tests.e2e.conftest import create_comparison, create_project_and_experiment


def test_investigation_and_counterfactual_flow_from_a_real_comparison(client):
    state = create_comparison(client)
    comparison_id = state["comparison"]["id"]

    investigation_resp = client.post("/api/v1/investigations", json={"comparison_id": comparison_id})
    assert investigation_resp.status_code == 201, investigation_resp.text
    investigation = investigation_resp.json()
    assert investigation["comparison_id"] == comparison_id
    assert investigation["changed_category"] == "CODE"

    investigation_get_resp = client.get(f"/api/v1/investigations/{investigation['id']}")
    assert investigation_get_resp.status_code == 200
    assert investigation_get_resp.json() == investigation

    counterfactual_resp = client.post("/api/v1/counterfactuals", json={"comparison_id": comparison_id})
    assert counterfactual_resp.status_code == 201, counterfactual_resp.text
    counterfactual = counterfactual_resp.json()
    assert counterfactual["comparison_id"] == comparison_id

    report_resp = client.get(
        f"/api/v1/reports/{comparison_id}",
        params={"investigation_id": investigation["id"], "counterfactual_id": counterfactual["id"]},
    )
    assert report_resp.status_code == 200, report_resp.text
    report = report_resp.json()
    assert report["investigation"]["available"] is True
    assert report["counterfactual"]["available"] is True


def test_investigation_422s_when_a_comparison_has_no_potential_contributor(client):
    project_id, experiment_id = create_project_and_experiment(client)
    from tests.e2e.conftest import create_run

    base_run_id = create_run(client, experiment_id)
    compare_run_id = create_run(client, experiment_id)

    compare_resp = client.post(
        f"/api/v1/runs/{base_run_id}/compare",
        json={"compare_run_id": compare_run_id},
    )
    assert compare_resp.status_code == 201
    comparison_id = compare_resp.json()["id"]

    resp = client.post("/api/v1/investigations", json={"comparison_id": comparison_id})
    assert resp.status_code == 422


def test_search_finds_a_real_persisted_project(client):
    project_id, _ = create_project_and_experiment(client)

    resp = client.get("/api/v1/search", params={"q": "E2E Project"})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["total"] >= 1
    assert any(item["entity_id"] == project_id for item in body["items"])


def test_dashboard_reflects_real_persisted_counts(client):
    before = client.get("/api/v1/dashboard").json()

    create_project_and_experiment(client)

    after = client.get("/api/v1/dashboard").json()
    assert after["total_projects"] == before["total_projects"] + 1
    assert after["total_experiments"] == before["total_experiments"] + 1
