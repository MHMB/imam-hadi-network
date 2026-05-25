"""``Loan`` and ``LoanParty``.

A loan has a single total amount, one topic, and N parties on each side.
``LoanParty.role`` distinguishes borrowers from lenders.  Invariant
(enforced by importer, not DB): ``Σ borrower amounts = Σ lender amounts =
loan.total_amount``.

Per-loan guarantor lives on ``Loan.guarantor_id`` (Phase 1 sample: only
set on year-1405 rows).  The four guarantor *slots* on a person sit on
``person_guarantor`` instead.
"""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy import Enum as SqlEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models import Base
from app.models.enums import LoanPartyRole
from app.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from app.models.import_ import Import
    from app.models.installment import Installment
    from app.models.person import Person
    from app.models.topic import LoanTopic


class Loan(Base, TimestampMixin):
    """One loan in one year — the central business entity."""

    __tablename__ = "loan"

    # --- required ---
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, init=False)
    persian_year: Mapped[int] = mapped_column(SmallInteger, nullable=False, index=True)
    loan_number: Mapped[str] = mapped_column(String(32), nullable=False)
    """Whatever the xlsm column ``ش`` / ``#ش`` contained (string for
    flexibility: legacy data sometimes carries trailing decimals)."""

    total_amount: Mapped[Decimal] = mapped_column(Numeric(18, 3), nullable=False)
    """In million toman.  ``numeric(18,3)`` preserves fractional millions
    such as ``5.5`` without binary-float rounding."""

    topic_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("loan_topic.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    import_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("import.id", ondelete="RESTRICT"),
        nullable=False,
    )

    # --- optional ---
    channel_number: Mapped[str | None] = mapped_column(String(32), default=None)
    guarantor_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("person.id", ondelete="RESTRICT"),
        index=True,
        default=None,
    )
    liaison_label: Mapped[str | None] = mapped_column(String(80), index=True, default=None)
    description: Mapped[str | None] = mapped_column(Text, default=None)

    # --- relationships ---
    # init=False on every relationship side — otherwise MappedAsDataclass
    # passes the relationship attribute (e.g. topic=None) through __init__,
    # and SQLAlchemy synchronises the FK columns (topic_id, import_id, ...)
    # to None to match.  We pass the FK ids directly in the writer; the
    # ORM objects are fetched separately when needed.
    topic: Mapped[LoanTopic] = relationship(init=False)
    guarantor: Mapped[Person | None] = relationship(
        foreign_keys=[guarantor_id],
        init=False,
    )
    import_: Mapped[Import] = relationship(
        back_populates="loans",
        foreign_keys=[import_id],
        init=False,
    )
    parties: Mapped[list[LoanParty]] = relationship(
        back_populates="loan",
        cascade="all, delete-orphan",
        order_by="LoanParty.display_order",
        init=False,
        default_factory=list,
    )

    __table_args__ = (
        UniqueConstraint("persian_year", "loan_number", name="unique_year_number"),
        CheckConstraint("total_amount > 0", name="total_amount_positive"),
    )


class LoanParty(Base):
    """A person on one side of a loan (borrower or lender).

    Phase 1 importer emits exactly one ``borrower`` party per loan with
    ``amount = loan.total_amount`` and N ``lender`` parties whose amounts
    sum to the same total.  Schema accepts any N-to-N combination — the
    parser is the only spot that would change for multi-borrower xlsm
    revisions or a future write-UI.
    """

    __tablename__ = "loan_party"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, init=False)
    loan_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("loan.id", ondelete="CASCADE"),
        nullable=False,
    )
    person_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("person.id", ondelete="RESTRICT"),
        nullable=False,
    )
    role: Mapped[LoanPartyRole] = mapped_column(
        SqlEnum(
            LoanPartyRole,
            native_enum=False,
            length=16,
            name="ck_loan_party_role",
            create_constraint=True,
            validate_strings=True,
        ),
        nullable=False,
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 3), nullable=False)
    display_order: Mapped[int] = mapped_column(SmallInteger, nullable=False)

    # --- relationships --- (init=False — see note on Loan.topic)
    loan: Mapped[Loan] = relationship(back_populates="parties", init=False)
    person: Mapped[Person] = relationship(init=False)
    installments: Mapped[list[Installment]] = relationship(
        back_populates="loan_party",
        cascade="all, delete-orphan",
        order_by="(Installment.due_persian_year, Installment.due_persian_month,"
        " Installment.due_day_of_month)",
        init=False,
        default_factory=list,
    )

    __table_args__ = (
        UniqueConstraint("loan_id", "role", "person_id", name="unique_role_person"),
        CheckConstraint("amount > 0", name="amount_positive"),
        # Composite indexes for the dashboard's hottest access patterns:
        # - loan detail   → (loan_id, role) to fetch borrowers / lenders separately
        # - person profile → (person_id, role) for per-person aggregation
        Index("ix_loan_party_loan_role", "loan_id", "role"),
        Index("ix_loan_party_person_role", "person_id", "role"),
    )
