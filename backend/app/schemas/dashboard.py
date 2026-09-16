from __future__ import annotations

import uuid

from pydantic import BaseModel


class RecentExperiment(BaseModel):
    id: uuid.UUID
    name: str
    project_id: uuid.UUID


class DashboardRead(BaseModel):
    total_projects: int
    total_experiments: int
    total_runs: int
    reproducible_runs: int
    partial_reproductions: int
    failed_reproductions: int
    insufficient_evidence: int
    active_jobs: int
    recent_experiments: list[RecentExperiment]
