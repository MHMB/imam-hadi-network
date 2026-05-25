"""Response shapes for /api/kpi."""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, Field


class KPIByYear(BaseModel):
    """One row per persian year present in the DB."""

    year: int
    loan_count: int = Field(ge=0)
    total: Decimal
    outstanding: Decimal


class KPIResponse(BaseModel):
    """Top-level dashboard KPIs (DESIGN.md §5.2 / §6.2.1)."""

    persons_total: int = Field(ge=0)
    loans_total: int = Field(ge=0)
    loans_active: int = Field(ge=0)
    loans_settled: int = Field(ge=0)
    total_amount: Decimal
    outstanding_total: Decimal
    overdue_installments: int = Field(ge=0)
    by_year: list[KPIByYear]
