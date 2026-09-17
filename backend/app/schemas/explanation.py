from __future__ import annotations

from pydantic import BaseModel


class ExplanationRead(BaseModel):
    status: str
    text: str
    evidence_ids: list[str]
    provider_name: str
