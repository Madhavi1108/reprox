from __future__ import annotations

import uuid

from pydantic import BaseModel


class SearchResultRead(BaseModel):
    entity_type: str
    entity_id: uuid.UUID
    project_id: uuid.UUID | None
    title: str
    snippet: str
    score: float
