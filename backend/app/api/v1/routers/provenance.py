"""GET /provenance/{run_id} (Phase 19).

Queries the real `provenance_nodes`/`provenance_edges` tables (Phase 16's
schema) for a given run. No phase before this one ever writes to those
tables from a live pipeline - Phase 16's `assemble_provenance_graph` is
only exercised in its own unit tests - so this endpoint will return an
empty graph for every run until a future phase wires actual ingestion.
The query itself is correct and forward-compatible; documented in
docs/API.md rather than left as a silent surprise.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.errors import NotFoundError
from app.db.models.core import ExperimentRun
from app.db.models.graph import ProvenanceEdge, ProvenanceNode
from app.db.session import get_db
from app.schemas.provenance import ProvenanceGraphRead

router = APIRouter(tags=["provenance"])


@router.get("/provenance/{run_id}", response_model=ProvenanceGraphRead)
def get_provenance(run_id: uuid.UUID, db: Session = Depends(get_db)) -> ProvenanceGraphRead:
    if db.get(ExperimentRun, run_id) is None:
        raise NotFoundError(f"run {run_id} not found")

    nodes = db.query(ProvenanceNode).filter(ProvenanceNode.run_id == run_id).all()
    node_ids = [n.id for n in nodes]
    edges = (
        db.query(ProvenanceEdge)
        .filter(ProvenanceEdge.from_node_id.in_(node_ids) | ProvenanceEdge.to_node_id.in_(node_ids))
        .all()
        if node_ids
        else []
    )
    return ProvenanceGraphRead(run_id=run_id, nodes=nodes, edges=edges)
