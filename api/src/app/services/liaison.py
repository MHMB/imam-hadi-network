"""رابط labels → people.  The admin links a label once; all its loans follow."""

from __future__ import annotations

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import FieldError
from app.importer.names import resolve_key
from app.models import AppUser, LiaisonAlias, Loan, Person
from app.schemas.person import LiaisonLink, LiaisonRow, PersonRef
from app.services.audit import record


async def list_liaisons(session: AsyncSession) -> list[LiaisonRow]:
    rows = (
        await session.execute(
            select(
                Loan.liaison_label,
                func.count().label("n"),
                func.max(Loan.liaison_person_id).label("pid"),
            )
            .where(Loan.liaison_label.is_not(None))
            .group_by(Loan.liaison_label)
            .order_by(func.count().desc())
        )
    ).all()
    confirmed = set((await session.execute(select(LiaisonAlias.label_key))).scalars())
    people = {
        p.id: p
        for p in (
            await session.execute(
                select(Person).where(Person.id.in_({r.pid for r in rows if r.pid}))
            )
        ).scalars()
    }
    return [
        LiaisonRow(
            label=r.liaison_label,
            loan_count=r.n,
            person=(
                PersonRef(id=p.id, full_name=p.full_name, phone=p.phone)
                if (p := people.get(r.pid)) is not None
                else None
            ),
            confirmed=resolve_key(r.liaison_label) in confirmed,
        )
        for r in rows
    ]


async def link_liaison(session: AsyncSession, user: AppUser, body: LiaisonLink) -> int:
    """Store the alias and relink every loan whose label has the same key.

    Returns the number of loans updated.
    """
    if body.person_id is not None and await session.get(Person, body.person_id) is None:
        raise FieldError("person_id", "این فرد پیدا نشد.")
    key = resolve_key(body.label)
    before = (
        await session.execute(select(LiaisonAlias.person_id).where(LiaisonAlias.label_key == key))
    ).one_or_none()

    await session.execute(
        insert(LiaisonAlias)
        .values(label_key=key, label=body.label, person_id=body.person_id)
        .on_conflict_do_update(
            index_elements=["label_key"], set_={"label": body.label, "person_id": body.person_id}
        )
    )
    labels = [
        lbl
        for lbl in (
            await session.execute(
                select(Loan.liaison_label).where(Loan.liaison_label.is_not(None)).distinct()
            )
        ).scalars()
        if resolve_key(lbl) == key
    ]
    relinked = (
        await session.execute(
            update(Loan)
            .where(Loan.liaison_label.in_(labels))
            .values(liaison_person_id=body.person_id)
            .returning(Loan.id)
        )
    ).all()
    await record(
        session,
        user,
        action="link",
        entity="liaison",
        entity_id=body.person_id or 0,
        before={"label": body.label, "person_id": before[0] if before else None},
        after={"label": body.label, "person_id": body.person_id, "labels": labels},
    )
    await session.commit()
    return len(relinked)
