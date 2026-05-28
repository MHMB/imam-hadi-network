"""Response shapes for /api/analytics/monthly."""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, Field


class MonthlyPeriod(BaseModel):
    persian_year: int
    persian_month: int = Field(ge=1, le=12)
    label_fa: str  # "خرداد ۱۴۰۴"


class NewLoansSummary(BaseModel):
    count: int = Field(ge=0)
    total_amount: Decimal


class InstallmentsDueByDay(BaseModel):
    day: int = Field(ge=1, le=31)
    count: int = Field(ge=0)
    paid_amount: Decimal
    unpaid_amount: Decimal


class InstallmentsDueSummary(BaseModel):
    count: int = Field(ge=0)
    amount_total: Decimal
    amount_paid: Decimal
    amount_unpaid: Decimal
    payment_rate_pct: float = Field(ge=0, le=100)  # 0 if total=0
    by_day: list[InstallmentsDueByDay]


class TopicBreakdownItem(BaseModel):
    topic_name: str
    count: int = Field(ge=0)
    total: Decimal


class PersonAmountItem(BaseModel):
    person_id: int
    full_name: str
    total: Decimal


class MonthlyAnalyticsResponse(BaseModel):
    period: MonthlyPeriod
    new_loans: NewLoansSummary
    installments_due: InstallmentsDueSummary
    new_loans_by_topic: list[TopicBreakdownItem]
    top_borrowers: list[PersonAmountItem]
    top_lenders: list[PersonAmountItem]
