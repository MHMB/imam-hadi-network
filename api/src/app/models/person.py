"""``Person`` + ``PersonGuarantor``.

Identity rule: each person is uniquely identified by their canonicalised
phone number.  ``national_code`` is reserved for Phase 2 (admins do not
record it today) and is nullable + unique-when-present.

Names are *not* keys — they are descriptive and may collide.  The legacy
xlsm uses names as keys (via ``VLOOKUP`` / ``SUMIFS``), which is exactly
the fragility we are migrating away from.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, Boolean, CheckConstraint, ForeignKey, String
from sqlalchemy import Enum as SqlEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models import Base
from app.models.enums import GuarantorRole
from app.models.mixins import TimestampMixin

if TYPE_CHECKING:
    pass


class Person(Base, TimestampMixin):
    """A member of the borrowing network.

    Plays one or more of three roles across loans: borrower, lender,
    guarantor.  Identity is the phone number; everything else is metadata.
    """

    __tablename__ = "person"

    # --- required ---
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, init=False)
    phone: Mapped[str] = mapped_column(String(32), nullable=False, unique=True, index=True)
    """Canonical form, e.g. ``+989121234567``.  See ``app.importer.phone``."""

    full_name: Mapped[str] = mapped_column(String(200), nullable=False)

    # --- optional ---
    phone_raw: Mapped[str | None] = mapped_column(String(64), default=None)
    """Exactly as the cell appeared in xlsm — kept for audit / forensics."""

    national_code: Mapped[str | None] = mapped_column(
        String(20),
        unique=True,
        index=True,
        default=None,
    )
    """Iranian national code; nullable in Phase 1, populated in Phase 2."""

    messenger: Mapped[str | None] = mapped_column(String(120), default=None)
    """Free-text — Telegram/WhatsApp/Eitaa handle, as written by admins."""

    is_verified: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default="false",
        default=False,
    )
    """Maps to ``تأیید`` in the legacy people sheet.  Filter only — no
    behaviour gating in Phase 1."""

    # --- relationships ---
    guarantor_links: Mapped[list[PersonGuarantor]] = relationship(
        back_populates="person",
        foreign_keys="PersonGuarantor.person_id",
        cascade="all, delete-orphan",
        default_factory=list,
    )


class PersonGuarantor(Base):
    """An ordered guarantor slot on a person's profile.

    Composite PK ``(person_id, role)`` enforces that each role can be
    filled at most once per person — there is exactly one "main" guarantor,
    one "secondary_2", etc., never two competing entries.
    """

    __tablename__ = "person_guarantor"

    person_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("person.id", ondelete="CASCADE"),
        primary_key=True,
    )
    role: Mapped[GuarantorRole] = mapped_column(
        SqlEnum(
            GuarantorRole,
            native_enum=False,
            length=16,
            name="ck_person_guarantor_role",
            create_constraint=True,
            validate_strings=True,
        ),
        primary_key=True,
    )
    guarantor_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("person.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    # --- relationships ---
    person: Mapped[Person] = relationship(
        back_populates="guarantor_links",
        foreign_keys=[person_id],
        default=None,
    )
    guarantor: Mapped[Person] = relationship(
        foreign_keys=[guarantor_id],
        default=None,
    )

    __table_args__ = (
        CheckConstraint(
            "person_id <> guarantor_id",
            name="self_guarantee_forbidden",
        ),
    )
