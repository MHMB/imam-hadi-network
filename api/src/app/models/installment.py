"""``Installment`` — one scheduled repayment.

Attached to a ``LoanParty`` (in Phase 1, always a lender-role party).
Dates are stored as ``(year, month, day)`` triples in the Jalali
calendar — never as UTC ``timestamp`` — so a server timezone change
cannot shift a due date by one day.

``paid_persian_date`` is reserved for Phase 2 (actual payment date).
For now ``status`` is derived from the green fill on the source cell.
"""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    ForeignKey,
    Index,
    Numeric,
    SmallInteger,
    Text,
    text,
)
from sqlalchemy import Enum as SqlEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models import Base
from app.models.enums import InstallmentStatus

if TYPE_CHECKING:
    from app.models.loan import LoanParty


class Installment(Base):
    """One row in a lender's repayment schedule for one loan."""

    __tablename__ = "installment"

    # --- required ---
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, init=False)
    loan_party_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("loan_party.id", ondelete="CASCADE"),
        nullable=False,
    )
    due_persian_year: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    due_persian_month: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    due_day_of_month: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 3), nullable=False)
    status: Mapped[InstallmentStatus] = mapped_column(
        SqlEnum(
            InstallmentStatus,
            native_enum=False,
            length=16,
            name="ck_installment_status",
            create_constraint=True,
            validate_strings=True,
        ),
        nullable=False,
    )

    # --- optional / future ---
    paid_persian_year: Mapped[int | None] = mapped_column(SmallInteger, default=None)
    paid_persian_month: Mapped[int | None] = mapped_column(SmallInteger, default=None)
    paid_persian_day: Mapped[int | None] = mapped_column(SmallInteger, default=None)
    """Reserved for Phase 2 — actual payment date.  Triple stored, never UTC."""

    notes: Mapped[str | None] = mapped_column(Text, default=None)

    # --- relationships --- (init=False — see note on Loan.topic)
    loan_party: Mapped[LoanParty] = relationship(back_populates="installments", init=False)

    __table_args__ = (
        CheckConstraint("due_persian_month BETWEEN 1 AND 12", name="due_month_valid"),
        CheckConstraint("due_day_of_month BETWEEN 1 AND 31", name="due_day_valid"),
        CheckConstraint("amount > 0", name="amount_positive"),
        CheckConstraint(
            "(paid_persian_year IS NULL) = (paid_persian_month IS NULL)"
            " AND (paid_persian_year IS NULL) = (paid_persian_day IS NULL)",
            name="paid_date_triple_consistent",
        ),
        CheckConstraint(
            "paid_persian_month IS NULL OR paid_persian_month BETWEEN 1 AND 12",
            name="paid_month_valid",
        ),
        CheckConstraint(
            "paid_persian_day IS NULL OR paid_persian_day BETWEEN 1 AND 31",
            name="paid_day_valid",
        ),
        # Hot-path: list unpaid installments sorted by due date
        # (overdue scan + person/loan timelines).  Partial index keeps it tiny.
        Index(
            "ix_installment_unpaid_due",
            "due_persian_year",
            "due_persian_month",
            "due_day_of_month",
            postgresql_where=text("status = 'unpaid'"),
        ),
        # Loan-party rollups (paid total, remaining)
        Index("ix_installment_party_status", "loan_party_id", "status"),
    )
