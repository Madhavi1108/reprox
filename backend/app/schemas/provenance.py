from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel


class ProvenanceNodeRead(BaseModel):
    id: uuid.UUID
    run_id: uuid.UUID
    node_type: str
    ref_table: str
    ref_id: uuid.UUID
    created_at: datetime

    model_config = {"from_attributes": True}


class ProvenanceEdgeRead(BaseModel):
    id: uuid.UUID
    from_node_id: uuid.UUID
    to_node_id: uuid.UUID
    edge_type: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ProvenanceGraphRead(BaseModel):
    run_id: uuid.UUID
    nodes: list[ProvenanceNodeRead]
    edges: list[ProvenanceEdgeRead]
