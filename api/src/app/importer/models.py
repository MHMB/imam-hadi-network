"""In-memory parsing model.

Pure ``@dataclass(frozen=True)`` types — no ORM, no DB.  Parsers return
trees of these; the writer (P2.8) converts them into SQLAlchemy rows in
one transaction.  Decoupling parsing from persistence keeps parsers
unit-testable without a database and makes ``--dry-run`` trivial.

The ``ParsedX`` shapes are intentionally close to the DB tables so the
writer is mostly field-for-field copying, but they're not the same:
parsed people carry ``phone_canonical_issue`` (an importer concern),
parsed loans carry ``source_sheet`` (xlsm metadata), etc.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from app.models.enums import (
    GuarantorRole,
    InstallmentStatus,
    IssueCategory,
    IssueSeverity,
    LoanPartyRole,
)


@dataclass(frozen=True, slots=True)
class ParsedIssue:
    """A finding the importer wants to surface.

    Mapped 1:1 to a ``data_issue`` row at write time.
    """

    severity: IssueSeverity
    category: IssueCategory
    message: str
    sheet: str | None = None
    cell: str | None = None
    context: dict[str, object] | None = None


@dataclass(frozen=True, slots=True)
class ParsedGuarantorLink:
    """A guarantor slot on a person — resolved from the legacy افراد sheet."""

    role: GuarantorRole
    guarantor_name: str
    """Name string as written in the xlsm — resolved to a Person id in the writer."""


@dataclass(frozen=True, slots=True)
class ParsedPerson:
    """One row from the افراد sheet."""

    full_name: str
    phone_canonical: str  # empty if the importer could not derive one
    phone_raw: str | None
    is_verified: bool = False
    messenger: str | None = None
    guarantor_links: tuple[ParsedGuarantorLink, ...] = ()


@dataclass(frozen=True, slots=True)
class ParsedInstallment:
    """One scheduled repayment for one lender party."""

    due_persian_year: int
    due_persian_month: int  # 1..12
    due_day_of_month: int  # 1..31
    amount: Decimal
    status: InstallmentStatus
    sheet: str | None = None
    cell: str | None = None  # e.g. "سال 1404!U5" — for issue context


@dataclass(frozen=True, slots=True)
class ParsedParty:
    """One borrower or lender on a loan."""

    role: LoanPartyRole
    person_name: str  # resolved to Person id in the writer
    amount: Decimal
    display_order: int
    installments: tuple[ParsedInstallment, ...] = ()


@dataclass(frozen=True, slots=True)
class ParsedLoan:
    """One loan + all its parties + all their installments."""

    persian_year: int
    loan_number: str
    total_amount: Decimal
    topic_name: str  # resolved to LoanTopic id in the writer
    parties: tuple[ParsedParty, ...] = ()
    channel_number: str | None = None
    guarantor_name: str | None = None
    liaison_label: str | None = None
    description: str | None = None
    source_sheet: str | None = None


@dataclass(slots=True)
class ParseResult:
    """Aggregate output of a full workbook parse.

    Mutable on purpose — parsers append to ``issues`` as they go.
    Everything else is built once.
    """

    topics: list[str] = field(default_factory=list)
    persons: list[ParsedPerson] = field(default_factory=list)
    loans: list[ParsedLoan] = field(default_factory=list)
    years_present: list[int] = field(default_factory=list)
    issues: list[ParsedIssue] = field(default_factory=list)
