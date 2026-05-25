"""Response shapes for /api/topics."""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, Field


class TopicSummary(BaseModel):
    """One row on the Topics page (DESIGN.md §6.2.6)."""

    id: int
    name: str
    loan_count: int = Field(ge=0)
    total: Decimal
    outstanding: Decimal
