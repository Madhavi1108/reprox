from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel

from app.db.models.enums import JobStatus, JobType


class JobRead(BaseModel):
    id: uuid.UUID
    job_type: JobType
    related_run_id: uuid.UUID | None
    related_comparison_id: uuid.UUID | None
    status: JobStatus
    progress_pct: int
    error_message: str | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None

    model_config = {"from_attributes": True}
