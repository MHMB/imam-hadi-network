"""Response shapes for /api/persons."""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, Field

from app.models.enums import GuarantorRole, InstallmentStatus


class PersonListItem(BaseModel):
    """Row on the persons list page (DESIGN.md §6.2.2)."""

    id: int
    full_name: str
    phone: str
    national_code: str | None = None
    is_verified: bool
    total_lent: Decimal
    total_borrowed: Decimal
    outstanding_receivable: Decimal
    outstanding_debt: Decimal
    net_capital: Decimal
    overdue_debt: Decimal = Decimal(0)  # past-due part of outstanding_debt
    guarantor: PersonRef | None = None  # member guarantor (افراد sheet, main slot)


class PersonGuarantorRef(BaseModel):
    role: GuarantorRole
    person: PersonRef


class PersonRef(BaseModel):
    """Minimal nested person reference used in profile detail responses."""

    id: int
    full_name: str
    phone: str


class PersonYearBreakdown(BaseModel):
    year: int
    as_borrower_loans: int = Field(ge=0)
    as_borrower_total: Decimal
    as_borrower_paid: Decimal
    as_borrower_remaining: Decimal
    as_lender_parties: int = Field(ge=0)
    as_lender_total: Decimal
    as_lender_paid: Decimal
    as_lender_remaining: Decimal


class PersonLifetime(BaseModel):
    receivable: Decimal
    debt: Decimal
    net_capital: Decimal


class PersonInstallmentRef(BaseModel):
    """An upcoming or overdue installment surfaced on the profile page."""

    loan_id: int
    loan_number: str
    counterparty_name: str
    due_persian_year: int
    due_persian_month: int
    due_day_of_month: int
    amount: Decimal
    status: InstallmentStatus
    role: str  # 'borrower' or 'lender' — which side the person is on for this loan


class GuaranteedLoan(BaseModel):
    """A loan this person guaranteed (loan.guarantor_id)."""

    loan_id: int
    loan_number: str
    persian_year: int
    borrower_name: str
    total: Decimal
    remaining: Decimal
    overdue: Decimal


class PersonGuarantees(BaseModel):
    """Exposure as a per-loan guarantor."""

    loan_count: int
    active_count: int
    total: Decimal  # Σ loan totals guaranteed
    remaining: Decimal  # still being repaid
    overdue: Decimal  # past-due part of remaining
    loans: list[GuaranteedLoan]


class GuarantorOption(BaseModel):
    """A member guarantor for the persons-list filter."""

    id: int
    full_name: str
    members: int


class PersonDetailResponse(BaseModel):
    person: PersonListItem
    guarantees: PersonGuarantees
    guarantors: list[PersonGuarantorRef]
    by_year: list[PersonYearBreakdown]
    lifetime: PersonLifetime
    upcoming: list[PersonInstallmentRef]
    overdue: list[PersonInstallmentRef]


PersonGuarantorRef.model_rebuild()
PersonListItem.model_rebuild()
