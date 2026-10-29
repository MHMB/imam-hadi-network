"""Payments: preview, record, void, list; and editing a loan's schedule."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from app.schemas.loan_write import JalaliDate


class AllocationIn(BaseModel):
    installment_id: int
    amount: Decimal = Field(gt=0, max_digits=18, decimal_places=3)


class PaymentPreviewRequest(BaseModel):
    amount: Decimal = Field(gt=0, max_digits=18, decimal_places=3)


class AllocationOut(BaseModel):
    installment_id: int
    lender_name: str
    due: tuple[int, int, int]
    installment_amount: Decimal
    remaining_before: Decimal
    amount: Decimal


class PaymentPreview(BaseModel):
    allocations: list[AllocationOut]
    credit: Decimal  # money beyond everything still owed on the loan
    remaining_after: Decimal


class PaymentCreate(BaseModel):
    amount: Decimal = Field(gt=0, max_digits=18, decimal_places=3)
    paid: JalaliDate
    note: str | None = Field(default=None, max_length=2000)
    allocations: list[AllocationIn] | None = None
    """``None`` = follow the schedule (oldest due first).  Given = the admin's split."""
    confirm_credit: bool = False
    """Must be true when part of the amount is not allocated (kept as the borrower's credit)."""


class PaymentOut(BaseModel):
    id: int
    amount: Decimal
    paid: tuple[int, int, int]
    credit: Decimal
    note: str | None
    created_by: str
    created_at: datetime
    voided_at: datetime | None
    allocations: list[AllocationOut]


class ScheduleRow(BaseModel):
    id: int | None = None  # existing installment; None = new
    year: int = Field(ge=1300, le=1500)
    month: int = Field(ge=1, le=12)
    day: int = Field(ge=1, le=31)
    amount: Decimal = Field(gt=0, max_digits=18, decimal_places=3)


class LenderScheduleEdit(BaseModel):
    party_id: int
    installments: list[ScheduleRow] = Field(min_length=1)


class ScheduleEdit(BaseModel):
    lenders: list[LenderScheduleEdit] = Field(min_length=1)
