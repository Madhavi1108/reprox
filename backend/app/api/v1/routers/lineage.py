"""GET /lineage/{run_id} (Phase 19).

Unlike /provenance, this endpoint is fully live: `ExperimentRun.parent_run_id`
and `ExperimentComparison` rows are populated by this same API (POST
/experiments/{id}/runs and POST /runs/{id}/compare), so Phase 15's
lineage graph is built from real data, not stubs.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.errors import NotFoundError
from app.db.models.comparison import ExperimentComparison
from app.db.models.core import ExperimentRun
from app.db.session import get_db
from app.lineage.graph import ComparisonLink, RunNode, ancestors, build_lineage_graph, descendants
from app.schemas.lineage import LineageEdgeRead, LineageRead

router = APIRouter(tags=["lineage"])


@router.get("/lineage/{run_id}", response_model=LineageRead)
def get_lineage(run_id: uuid.UUID, db: Session = Depends(get_db)) -> LineageRead:
    run = db.get(ExperimentRun, run_id)
    if run is None:
        raise NotFoundError(f"run {run_id} not found")

    # All runs under the same experiment are the candidate node set - the
    # lineage graph for a single run is only ever a subtree of its siblings.
    sibling_runs = db.query(ExperimentRun).filter(ExperimentRun.experiment_id == run.experiment_id).all()
    run_nodes = [RunNode(run_id=r.id, parent_run_id=r.parent_run_id, run_type=r.run_type) for r in sibling_runs]

    run_ids = [r.id for r in sibling_runs]
    comparisons = (
        db.query(ExperimentComparison)
        .filter(ExperimentComparison.base_run_id.in_(run_ids), ExperimentComparison.compare_run_id.in_(run_ids))
        .all()
    )
    comparison_links = [ComparisonLink(base_run_id=c.base_run_id, compare_run_id=c.compare_run_id) for c in comparisons]

    graph = build_lineage_graph(run_nodes, comparison_links)

    return LineageRead(
        run_id=run_id,
        ancestors=ancestors(graph, run_id),
        descendants=descendants(graph, run_id),
        edges=[
            LineageEdgeRead(from_run_id=e.from_run_id, to_run_id=e.to_run_id, edge_type=e.edge_type.value)
            for e in graph.edges
        ],
    )
