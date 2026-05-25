"""``Import`` and ``DataIssue``.

One ``Import`` row per xlsm processed.  ``source_sha256`` is unique, so
re-uploading the same file short-circuits via the existing row.  Loans
written by an import keep a FK to it (``loan.import_id``) for audit.

``DataIssue`` is denormalized — every importer finding becomes a row with
``severity`` + ``category`` + ``cell`` so the Data Quality page (P7) can
paginate and filter without joining xlsm artifacts.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy import Enum as SqlEnum
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models import Base
from app.models.enums import ImportStatus, IssueCategory, IssueSeverity

if TYPE_CHECKING:
    from app.models.loan import Loan


class Import(Base):
    """One run of the importer over one xlsm file."""

    __tablename__ = "import"

    # --- required ---
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, init=False)
    source_sha256: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    source_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    years_imported: Mapped[list[int]] = mapped_column(ARRAY(Integer), nullable=False)
    status: Mapped[ImportStatus] = mapped_column(
        SqlEnum(
            ImportStatus,
            native_enum=False,
            length=16,
            name="ck_import_status",
            create_constraint=True,
            validate_strings=True,
        ),
        nullable=False,
    )

    # --- optional ---
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        init=False,
    )
    duration_ms: Mapped[int | None] = mapped_column(Integer, default=None)
    report: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default="{}",
        default_factory=dict,
    )
    error_message: Mapped[str | None] = mapped_column(Text, default=None)

    # --- relationships --- (init=False — see note on Loan.topic)
    loans: Mapped[list[Loan]] = relationship(
        back_populates="import_",
        passive_deletes="all",  # we use ON DELETE RESTRICT on loan.import_id
        init=False,
        default_factory=list,
    )
    issues: Mapped[list[DataIssue]] = relationship(
        back_populates="import_",
        cascade="all, delete-orphan",
        order_by="DataIssue.severity, DataIssue.category",
        init=False,
        default_factory=list,
    )


class DataIssue(Base):
    """One thing the importer flagged about an xlsm — error, warning, or info."""

    __tablename__ = "data_issue"

    # --- required ---
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, init=False)
    import_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("import.id", ondelete="CASCADE"),
        nullable=False,
    )
    severity: Mapped[IssueSeverity] = mapped_column(
        SqlEnum(
            IssueSeverity,
            native_enum=False,
            length=16,
            name="ck_data_issue_severity",
            create_constraint=True,
            validate_strings=True,
        ),
        nullable=False,
    )
    category: Mapped[IssueCategory] = mapped_column(
        SqlEnum(
            IssueCategory,
            native_enum=False,
            length=32,
            name="ck_data_issue_category",
            create_constraint=True,
            validate_strings=True,
        ),
        nullable=False,
    )
    message: Mapped[str] = mapped_column(Text, nullable=False)

    # --- optional ---
    sheet: Mapped[str | None] = mapped_column(String(120), default=None)
    cell: Mapped[str | None] = mapped_column(String(40), default=None)
    """e.g. ``سال 1404!O5``.  Free text, copy-to-clipboard on the issues
    page so admins can paste it into the Excel name box."""

    context: Mapped[dict[str, Any] | None] = mapped_column(JSONB, default=None)

    # --- relationships --- (init=False — see note on Loan.topic)
    import_: Mapped[Import] = relationship(back_populates="issues", init=False)

    __table_args__ = (Index("ix_data_issue_import_severity", "import_id", "severity"),)
