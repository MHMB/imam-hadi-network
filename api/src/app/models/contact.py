"""How to reach a person: one row per platform handle, one marked default."""

from __future__ import annotations

from sqlalchemy import BigInteger, Boolean, ForeignKey, Index, String, text
from sqlalchemy import Enum as SqlEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base
from app.models.enums import Platform


def platform_enum(name: str) -> SqlEnum:
    return SqlEnum(
        Platform,
        native_enum=False,
        length=16,
        name=name,
        create_constraint=True,
        validate_strings=True,
        values_callable=lambda e: [m.value for m in e],
    )


class PersonContact(Base):
    __tablename__ = "person_contact"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, init=False)
    person_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("person.id", ondelete="CASCADE"), nullable=False
    )
    platform: Mapped[Platform] = mapped_column(platform_enum("ck_person_contact_platform"))
    handle: Mapped[str] = mapped_column(String(120), nullable=False)
    """@username, phone number or link — whatever reaches them on that platform."""
    is_default: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )

    __table_args__ = (
        Index("ix_person_contact_person", "person_id"),
        # At most one default contact per person.
        Index(
            "uq_person_contact_default",
            "person_id",
            unique=True,
            postgresql_where=text("is_default"),
        ),
    )


class LiaisonAlias(Base):
    """How a رابط label from the sheet maps to a person (set once by the admin).

    ``person_id`` NULL means the label is a channel, not a person (e.g. «روابط»).
    The importer applies these on every import so links survive re-imports.
    """

    __tablename__ = "liaison_alias"

    label_key: Mapped[str] = mapped_column(String(80), primary_key=True)
    """``resolve_key`` of the label (spacing / ی-ک variants collapse together)."""
    label: Mapped[str] = mapped_column(String(80), nullable=False)
    person_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("person.id", ondelete="CASCADE"), nullable=True, default=None
    )


class PersonAlias(Base):
    """Another spelling of a merged person's name.

    The importer maps the name to ``person_id`` on every import, so people
    an admin merged stay merged when the workbook is uploaded again.
    """

    __tablename__ = "person_alias"

    name_key: Mapped[str] = mapped_column(String(200), primary_key=True)
    """``resolve_key`` of the merged-away name."""
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    person_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("person.id", ondelete="CASCADE"), nullable=False, index=True
    )
