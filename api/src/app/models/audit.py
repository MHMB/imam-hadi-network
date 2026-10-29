"""Who changed what: ``app_user`` and the append-only ``audit_log``.

Identity comes from Traefik basic-auth (one htpasswd line per staff member);
the API only reads the username Traefik already verified.  Every write in
the app appends one ``audit_log`` row with the entity's state before and
after the change, so any edit can be reviewed and reversed by hand.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base


class AppUser(Base):
    """A staff member, upserted on first request by username."""

    __tablename__ = "app_user"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, init=False)
    username: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, init=False
    )


class AuditLog(Base):
    """One write: action on an entity, with full before / after snapshots."""

    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, init=False)
    user_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("app_user.id", ondelete="RESTRICT"), nullable=True
    )
    action: Mapped[str] = mapped_column(String(32), nullable=False)  # create | update | void | …
    entity: Mapped[str] = mapped_column(String(32), nullable=False)  # loan | person | payment | …
    entity_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    before: Mapped[dict[str, Any] | None] = mapped_column(JSONB, default=None)
    after: Mapped[dict[str, Any] | None] = mapped_column(JSONB, default=None)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, init=False
    )

    __table_args__ = (Index("ix_audit_log_entity", "entity", "entity_id", "created_at"),)
