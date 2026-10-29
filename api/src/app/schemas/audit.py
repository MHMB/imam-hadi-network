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
    # Display names for id fields: {"topic_id": {"23": "خانه"}, "guarantor_id": {...}}
    names: dict[str, dict[str, str]] = {}


class MeResponse(BaseModel):
    username: str
    role: str
