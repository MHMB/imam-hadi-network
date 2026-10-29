"""Append-only audit trail: every write records the entity before and after."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any

from sqlalchemy import inspect, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AppUser, AuditLog, LoanTopic, Payment, Person
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


# id fields shown by name in the history, and the table each points at.
_PERSON_FIELDS = ("guarantor_id", "liaison_person_id", "payer_id", "person_id", "borrower_id")
_TOPIC_FIELDS = ("topic_id",)


async def _names(session: AsyncSession, logs: list[AuditLog]) -> dict[str, dict[str, str]]:
    """One lookup per table for every id an entry's before/after mentions."""
    ids: dict[str, set[int]] = {"person": set(), "topic": set()}
    for log in logs:
        for snap in (log.before or {}, log.after or {}):
            for f, v in snap.items():
                if isinstance(v, int) and f in _PERSON_FIELDS:
                    ids["person"].add(v)
                elif isinstance(v, int) and f in _TOPIC_FIELDS:
                    ids["topic"].add(v)
    people: dict[int, str] = {}
    topics: dict[int, str] = {}
    if ids["person"]:
        q = select(Person.id, Person.full_name).where(Person.id.in_(ids["person"]))
        people = dict((await session.execute(q)).tuples().all())
    if ids["topic"]:
        q = select(LoanTopic.id, LoanTopic.name).where(LoanTopic.id.in_(ids["topic"]))
        topics = dict((await session.execute(q)).tuples().all())
    out: dict[str, dict[str, str]] = {}
    for f in _PERSON_FIELDS:
        out[f] = {str(k): v for k, v in people.items()}
    for f in _TOPIC_FIELDS:
        out[f] = {str(k): v for k, v in topics.items()}
    return out


async def history(session: AsyncSession, entity: str, entity_id: int) -> list[AuditEntry]:
    """Entries for one entity, newest first.  A loan's history also lists its
    payments (recorded and voided), so the loan page tells the whole story."""
    match = (AuditLog.entity == entity) & (AuditLog.entity_id == entity_id)
    if entity == "loan":
        payment_ids = select(Payment.id).where(Payment.loan_id == entity_id)
        match = match | ((AuditLog.entity == "payment") & AuditLog.entity_id.in_(payment_ids))
    rows = (
        await session.execute(
            select(AuditLog, AppUser.username)
            .outerjoin(AppUser, AppUser.id == AuditLog.user_id)
            .where(match)
            .order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
        )
    ).all()
    names = await _names(session, [log for log, _ in rows])
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
            names={
                f: m
                for f, m in names.items()
                if m and f in {*(log.before or {}), *(log.after or {})}
            },
        )
        for log, username in rows
    ]
