"""Fold duplicate person rows (the same human typed several ways) into one."""

from __future__ import annotations

from sqlalchemy import and_, delete, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.errors import FieldError
from app.importer.names import resolve_key
from app.models import (
    AppUser,
    LiaisonAlias,
    Loan,
    LoanParty,
    Payment,
    Person,
    PersonAlias,
    PersonContact,
    PersonGuarantor,
)
from app.schemas.person import PersonMerge
from app.services.audit import record


async def merge_persons(
    session: AsyncSession, user: AppUser, keep_id: int, body: PersonMerge
) -> Person | None:
    """Move every reference from ``body.drop_ids`` to ``keep_id`` and delete them.

    Each dropped name becomes a :class:`PersonAlias`, so the next workbook
    import maps it to the kept person instead of re-creating the duplicate.
    """
    keep = await session.get(Person, keep_id)
    if keep is None:
        return None
    ids = sorted(set(body.drop_ids))
    if keep_id in ids:
        raise FieldError("drop_ids", "یک نفر را نمی‌توان با خودش ادغام کرد.")
    drops = list((await session.execute(select(Person).where(Person.id.in_(ids)))).scalars())
    if len(drops) != len(ids):
        raise FieldError("drop_ids", "این فرد پیدا نشد.")

    # Both on one loan in the same role would break unique_role_person.
    other = aliased(LoanParty)
    clash = await session.scalar(
        select(LoanParty.loan_id)
        .join(other, and_(other.loan_id == LoanParty.loan_id, other.role == LoanParty.role))
        .where(LoanParty.person_id == keep_id, other.person_id.in_(ids))
        .limit(1)
    )
    if clash is not None:
        raise FieldError("drop_ids", "این افراد در یک قرض با نقش یکسان آمده‌اند؛ ادغام ممکن نیست.")

    merged = "، ".join(d.full_name for d in drops)
    old_name = keep.full_name

    for col in (LoanParty.person_id, Loan.guarantor_id, Loan.liaison_person_id, Payment.payer_id):
        await session.execute(update(col.class_).where(col.in_(ids)).values({col.key: keep_id}))
    await session.execute(
        update(PersonContact)
        .where(PersonContact.person_id.in_(ids))
        .values(person_id=keep_id, is_default=False)
    )
    for alias_col in (LiaisonAlias.person_id, PersonAlias.person_id):
        await session.execute(
            update(alias_col.class_).where(alias_col.in_(ids)).values(person_id=keep_id)
        )
    # Guarantor slots: the kept person's own slot wins; theirs fill the gaps.
    slots = (
        await session.execute(
            select(PersonGuarantor.role, PersonGuarantor.guarantor_id).where(
                PersonGuarantor.person_id.in_(ids)
            )
        )
    ).all()
    for role, guarantor_id in slots:
        await session.execute(
            insert(PersonGuarantor)
            .values(person_id=keep_id, role=role, guarantor_id=guarantor_id)
            .on_conflict_do_nothing()
        )
    await session.execute(
        update(PersonGuarantor)
        .where(PersonGuarantor.guarantor_id.in_(ids))
        .values(guarantor_id=keep_id)
    )
    await session.execute(
        delete(PersonGuarantor).where(
            PersonGuarantor.person_id == keep_id, PersonGuarantor.guarantor_id == keep_id
        )
    )

    keep.is_verified = keep.is_verified or any(d.is_verified for d in drops)
    keep.bank_account = keep.bank_account or next(
        (d.bank_account for d in drops if d.bank_account), None
    )
    keep.messenger = keep.messenger or next((d.messenger for d in drops if d.messenger), None)
    names = [d.full_name for d in drops]
    if body.full_name and body.full_name.strip() != old_name:
        names.append(old_name)
        keep.full_name = body.full_name.strip()
    for name in names:
        key = resolve_key(name)
        if key and key != resolve_key(keep.full_name):
            await session.execute(
                insert(PersonAlias)
                .values(name_key=key, name=name, person_id=keep_id)
                .on_conflict_do_update(
                    index_elements=["name_key"], set_={"name": name, "person_id": keep_id}
                )
            )
    await session.flush()
    await session.execute(
        delete(Person).where(Person.id.in_(ids)).execution_options(synchronize_session=False)
    )
    await record(
        session,
        user,
        action="merge",
        entity="person",
        entity_id=keep_id,
        before={"full_name": old_name, "merged": merged},
        after={"full_name": keep.full_name},
    )
    await session.commit()
    return keep
