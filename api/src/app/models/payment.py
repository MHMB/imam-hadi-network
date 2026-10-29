"""Money that actually arrived, and how it was spread over installments.

``payment`` is what the borrower paid (amount, Jalali date typed by the
admin).  ``payment_allocation`` splits it over installments; the part not
allocated to any installment is ``credit`` — a confirmed over-payment held
for the borrower.  ``installment.amount_paid`` is kept equal to the sum of
its live (not voided) allocations in the same transaction.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    SmallInteger,
    Text,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base


class Payment(Base):
    __tablename__ = "payment"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, init=False)
    loan_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("loan.id", ondelete="CASCADE"), nullable=False, index=True
    )
    payer_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("person.id", ondelete="RESTRICT"), nullable=False
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 3), nullable=False)
    paid_persian_year: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    paid_persian_month: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    paid_persian_day: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    credit: Mapped[Decimal] = mapped_column(
        Numeric(18, 3), nullable=False, default=Decimal(0), server_default=text("0")
    )
    """Part of ``amount`` not allocated to any installment (confirmed over-payment)."""
    note: Mapped[str | None] = mapped_column(Text, default=None)
    created_by: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("app_user.id", ondelete="RESTRICT"), default=None
    )
    voided_by: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("app_user.id", ondelete="RESTRICT"), default=None
    )
    voided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, init=False
    )

    __table_args__ = (
        CheckConstraint("amount > 0", name="amount_positive"),
        CheckConstraint("credit >= 0 AND credit <= amount", name="credit_range"),
        CheckConstraint("paid_persian_month BETWEEN 1 AND 12", name="paid_month_valid"),
        CheckConstraint("paid_persian_day BETWEEN 1 AND 31", name="paid_day_valid"),
    )


class PaymentAllocation(Base):
    __tablename__ = "payment_allocation"

    payment_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("payment.id", ondelete="CASCADE"), primary_key=True
    )
    installment_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("installment.id", ondelete="CASCADE"), primary_key=True
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 3), nullable=False)

    __table_args__ = (
        CheckConstraint("amount > 0", name="amount_positive"),
        Index("ix_payment_allocation_installment", "installment_id"),
    )
