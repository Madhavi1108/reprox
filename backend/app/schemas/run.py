from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel

from app.db.models.enums import RunStatus, RunType


class RunCreate(BaseModel):
    run_type: RunType = RunType.ORIGINAL
    parent_run_id: uuid.UUID | None = None


class RunRead(BaseModel):
    id: uuid.UUID
    experiment_id: uuid.UUID
    run_type: RunType
    parent_run_id: uuid.UUID | None
    status: RunStatus
    exit_code: int | None
    error_message: str | None
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class RunCreateResponse(BaseModel):
    run: RunRead
    job_id: uuid.UUID
