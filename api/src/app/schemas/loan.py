"""Response shapes for /api/loans."""

from __future__ import annotations

from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field

from app.models.enums import InstallmentStatus
from app.schemas.person import PersonRef

LoanStatus = Literal["active", "settled"]


class LoanListItem(BaseModel):
    """Row on the loans list page (DESIGN.md §6.2.4)."""

    id: int
    persian_year: int
    loan_number: str
    channel_number: str | None
    topic_name: str
    borrower_name: str
    liaison_label: str | None
    total: Decimal
    paid: Decimal
    remaining: Decimal
    status: LoanStatus


class InstallmentRef(BaseModel):
    due_persian_year: int
    due_persian_month: int
    due_day_of_month: int
    amount: Decimal
    status: InstallmentStatus


class LoanPartyRef(BaseModel):
    party_id: int
    person: PersonRef
    amount: Decimal


class LenderPartyRef(LoanPartyRef):
    paid: Decimal
    remaining: Decimal
    installments: list[InstallmentRef]


class LoanTotals(BaseModel):
    total: Decimal
    paid: Decimal
    remaining: Decimal
    settled: bool


class TopicRef(BaseModel):
    id: int
    name: str


class LoanDetailResponse(BaseModel):
    """Response shape for /api/loans/{id} (DESIGN.md §5.2)."""

    loan: dict[str, object] = Field(
        default_factory=dict,
        description=(
            "Loan-level fields: id, persian_year, loan_number, channel_number, "
            "total_amount, liaison_label, description"
        ),
    )
    topic: TopicRef
    guarantor: PersonRef | None
    borrowers: list[LoanPartyRef]
    lenders: list[LenderPartyRef]
    totals: LoanTotals
