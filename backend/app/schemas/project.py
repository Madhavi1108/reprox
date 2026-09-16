from __future__ import annotations

import re
import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

_SLUG_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    slug: str = Field(min_length=1, max_length=220)
    description: str | None = None

    @field_validator("slug")
    @classmethod
    def validate_slug(cls, value: str) -> str:
        if not _SLUG_RE.match(value):
            raise ValueError("slug must be lowercase alphanumeric segments separated by hyphens")
        return value


class ProjectRead(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    description: str | None
    owner_user_id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
