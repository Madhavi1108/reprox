from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class ExperimentCreate(BaseModel):
    project_id: uuid.UUID
    name: str = Field(min_length=1, max_length=200)
    description: str | None = None
    workload_type: str = Field(default="sklearn_tabular", max_length=50)
    entrypoint_script: str = Field(min_length=1, max_length=300)


class ExperimentRead(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    name: str
    description: str | None
    workload_type: str
    entrypoint_script: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
