"""Reusable column-set mixins."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, func
from sqlalchemy.orm import Mapped, mapped_column


class TimestampMixin:
    """Adds ``created_at`` (immutable) and ``updated_at`` (auto-bumped on update).

    ``init=False`` keeps these columns out of the dataclass constructor —
    they are DB-managed.  Callers never set them by hand.
    """

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        init=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
        init=False,
    )
