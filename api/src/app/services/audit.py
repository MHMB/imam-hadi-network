"""Append-only audit trail: every write records the entity before and after."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any

from sqlalchemy import inspect, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AppUser, AuditLog
from app.schemas.audit import AuditEntry

_SKIP = {"created_at", "updated_at"}


def snapshot(obj: Any) -> dict[str, Any]:
    """Column values of an ORM row as JSON-safe data (money stays exact as text)."""

    def safe(v: Any) -> Any:
        if isinstance(v, Decimal):
            return str(v)
        if isinstance(v, Enum):
            return v.value
        if isinstance(v, date | datetime):
            return v.isoformat()
        return v

    return {
        a.key: safe(getattr(obj, a.key))
        for a in inspect(obj).mapper.column_attrs
        if a.key not in _SKIP
    }


async def record(
    session: AsyncSession,
    user: AppUser,
    *,
    action: str,
    entity: str,
    entity_id: int,
    before: dict[str, Any] | None,
    after: dict[str, Any] | None,
) -> None:
    """Add one audit row to the caller's transaction (committed with the change)."""
    session.add(
        AuditLog(
            user_id=user.id,
            action=action,
            entity=entity,
            entity_id=entity_id,
            before=before,
            after=after,
        )
    )


async def history(session: AsyncSession, entity: str, entity_id: int) -> list[AuditEntry]:
    rows = (
        await session.execute(
            select(AuditLog, AppUser.username)
            .outerjoin(AppUser, AppUser.id == AuditLog.user_id)
            .where(AuditLog.entity == entity, AuditLog.entity_id == entity_id)
            .order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
        )
    ).all()
    return [
        AuditEntry(
            id=log.id,
            at=log.created_at,
            username=username or "—",
            action=log.action,
            entity=log.entity,
            entity_id=log.entity_id,
            before=log.before,
            after=log.after,
        )
        for log, username in rows
    ]
