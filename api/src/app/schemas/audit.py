"""Response shapes for the audit trail and the current user."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel


class AuditEntry(BaseModel):
    id: int
    at: datetime
    username: str
    action: str
    entity: str
    entity_id: int
    before: dict[str, Any] | None
    after: dict[str, Any] | None


class MeResponse(BaseModel):
    username: str
    role: str
