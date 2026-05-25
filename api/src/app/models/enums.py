"""Domain enumerations.

All values are stored as plain strings in Postgres (column type ``VARCHAR``
+ a ``CHECK`` constraint) rather than native ``ENUM`` types — see
DESIGN.md §3.1 for the rationale (cheap to evolve, no ``ALTER TYPE`` dance).

Use ``SqlEnum(Foo, native_enum=False)`` when binding these to columns;
that gives compile-time type safety on the Python side and an in-table
``CHECK`` on the DB side, without minting Postgres enum types.
"""

from __future__ import annotations

from enum import StrEnum


class GuarantorRole(StrEnum):
    """Ordered slots a person's main + secondary guarantors fill (4 max)."""

    main = "main"
    secondary_2 = "secondary_2"
    secondary_3 = "secondary_3"
    secondary_4 = "secondary_4"


class LoanPartyRole(StrEnum):
    """Either side of a loan — borrowers and lenders share one table."""

    borrower = "borrower"
    lender = "lender"


class InstallmentStatus(StrEnum):
    """Repayment installment state.

    Derived from the cell fill colour in the source xlsm (``#00B050`` = paid,
    anything else = unpaid).  Phase 2 will add intermediate states once
    actual payment dates are recorded.
    """

    paid = "paid"
    unpaid = "unpaid"


class ImportStatus(StrEnum):
    """Lifecycle of one xlsm import."""

    pending = "pending"
    running = "running"
    success = "success"
    failed = "failed"


class IssueSeverity(StrEnum):
    """Severity bucket for an importer ``DataIssue``."""

    error = "error"
    warning = "warning"
    info = "info"


class IssueCategory(StrEnum):
    """Categorical type of an importer ``DataIssue``.

    Open list — extend when the importer learns to detect new problems.
    Persian labels live in the frontend i18n map (DESIGN.md §6.5), keyed
    off these identifiers.
    """

    broken_ref = "broken_ref"
    total_mismatch = "total_mismatch"
    unresolved_person = "unresolved_person"
    unknown_topic = "unknown_topic"
    duplicate_phone = "duplicate_phone"
    bad_day = "bad_day"
    color_anomaly = "color_anomaly"
    unknown_phone_format = "unknown_phone_format"
    orphan_row = "orphan_row"
    missing_day = "missing_day"
    missing_amount = "missing_amount"
