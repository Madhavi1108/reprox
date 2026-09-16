from __future__ import annotations

import uuid

from pydantic import BaseModel


class LineageEdgeRead(BaseModel):
    from_run_id: uuid.UUID
    to_run_id: uuid.UUID
    edge_type: str


class LineageRead(BaseModel):
    run_id: uuid.UUID
    ancestors: list[uuid.UUID]
    descendants: list[uuid.UUID]
    edges: list[LineageEdgeRead]
