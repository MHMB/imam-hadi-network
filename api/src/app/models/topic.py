"""``LoanTopic`` — catalog of loan purposes (موضوع).

Global, not year-scoped (admin-confirmed).  Seeded from the legacy
``موضوعات`` sheet via the ``0002_seed_topics`` migration.  Importer
upserts any new names found in newer xlsm files.
"""

from __future__ import annotations

from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base


class LoanTopic(Base):
    """One loan category (e.g. ``درمان``, ``ازدواج``)."""

    __tablename__ = "loan_topic"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, init=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False, unique=True, index=True)

    legacy_num: Mapped[int | None] = mapped_column(Integer, default=None)
    """Mirrors the ``num`` column on the legacy ``موضوعات`` sheet.  Only
    ``0`` (unknown) was set in the source — kept for traceability."""
