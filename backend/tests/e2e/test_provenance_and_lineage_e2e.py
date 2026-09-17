"""Phase 31: provenance graph + lineage flows against a real persisted
comparison. /provenance is honestly empty (Phase 16's tables are never
written to by any phase, documented in app/api/v1/routers/provenance.py) -
this test asserts that documented behavior end-to-end rather than
pretending it's populated. /lineage is fully live - built from the same
runs/comparisons this API just wrote."""

from __future__ import annotations

import uuid

from tests.e2e.conftest import create_comparison


def test_provenance_is_empty_but_well_formed_for_a_real_run(client):
    state = create_comparison(client)
    run_id = state["base_run_id"]

    resp = client.get(f"/api/v1/provenance/{run_id}")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["run_id"] == run_id
    assert body["nodes"] == []
    assert body["edges"] == []


def test_provenance_404s_for_an_unknown_run(client):
    resp = client.get(f"/api/v1/provenance/{uuid.uuid4()}")
    assert resp.status_code == 404


def test_lineage_reflects_the_real_persisted_comparison(client):
    state = create_comparison(client)
    base_run_id = state["base_run_id"]
    compare_run_id = state["compare_run_id"]

    resp = client.get(f"/api/v1/lineage/{base_run_id}")
    assert resp.status_code == 200, resp.text
    body = resp.json()

    assert body["run_id"] == base_run_id
    edge_pairs = {(e["from_run_id"], e["to_run_id"], e["edge_type"]) for e in body["edges"]}
    assert (base_run_id, compare_run_id, "COMPARES_WITH") in edge_pairs
