"""Response shapes for /api/installments/overdue."""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, Field

from app.schemas.person import PersonRef


class OverdueInstallmentItem(BaseModel):
    """One overdue installment, fully denormalized for table display."""

    installment_id: int
    loan_id: int
    loan_number: str
    persian_year: int
    topic_name: str
    borrower: PersonRef
    lender: PersonRef
    guarantor: PersonRef | None
    due_persian_year: int
    due_persian_month: int
    due_day_of_month: int
    amount: Decimal
    days_overdue: int = Field(ge=0)
