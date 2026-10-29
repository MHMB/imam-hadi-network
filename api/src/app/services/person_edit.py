"""Editing a person's profile: name, phone (required), bank account, contacts."""

from __future__ import annotations

import re
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import FieldError
from app.importer.phone import canonicalize
from app.models import AppUser, Person, PersonContact
from app.schemas.person import ContactRef, PersonProfile, PersonUpdate
from app.services.audit import record, snapshot

_PERSIAN_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")
_BANK_RE = re.compile(r"^(IR)?\d{8,26}$")


async def get_profile(session: AsyncSession, person: Person) -> PersonProfile:
    contacts = (
        await session.execute(
            select(PersonContact)
            .where(PersonContact.person_id == person.id)
            .order_by(PersonContact.is_default.desc(), PersonContact.id)
        )
    ).scalars()
    return PersonProfile(
        bank_account=person.bank_account,
        messenger=person.messenger,
        contacts=[
            ContactRef(platform=c.platform, handle=c.handle, is_default=c.is_default)
            for c in contacts
        ],
    )


def _state(person: Person, profile: PersonProfile) -> dict[str, Any]:
    return {**snapshot(person), "contacts": [c.model_dump(mode="json") for c in profile.contacts]}


def _bank(value: str | None) -> str | None:
    if value is None or not value.strip():
        return None
    folded = re.sub(r"[\s\-]", "", value.translate(_PERSIAN_DIGITS)).upper()
    if not _BANK_RE.match(folded):
        raise FieldError(
            "bank_account", "شماره حساب، کارت یا شبا معتبر نیست (فقط رقم، ۸ تا ۲۶ رقم)."
        )
    return folded


def _valid_phone(raw: str) -> tuple[str, str]:
    phone = canonicalize(raw)
    if phone.issue is not None or not phone.canonical:
        raise FieldError("phone", "شماره تماس معتبر نیست. مثال: ۰۹۱۲۱۲۳۴۵۶۷")
    return phone.canonical, phone.raw


async def _phone_free(session: AsyncSession, canonical: str, person_id: int | None) -> None:
    clash = (
        await session.execute(
            select(Person.full_name).where(Person.phone == canonical, Person.id != (person_id or 0))
        )
    ).scalar_one_or_none()
    if clash is not None:
        raise FieldError("phone", f"این شماره قبلاً برای «{clash}» ثبت شده است.", code="duplicate")


async def create_person(session: AsyncSession, user: AppUser, full_name: str, phone: str) -> Person:
    name = full_name.strip()
    if not name:
        raise FieldError("full_name", "نام نمی‌تواند خالی باشد.")
    canonical, raw = _valid_phone(phone)
    await _phone_free(session, canonical, None)
    person = Person(phone=canonical, full_name=name, phone_raw=raw)
    session.add(person)
    await session.flush()
    await record(
        session,
        user,
        action="create",
        entity="person",
        entity_id=person.id,
        before=None,
        after=snapshot(person),
    )
    await session.commit()
    return person


async def update_person(
    session: AsyncSession, user: AppUser, person_id: int, body: PersonUpdate
) -> Person | None:
    person = await session.get(Person, person_id, with_for_update=True)
    if person is None:
        return None
    before = _state(person, await get_profile(session, person))

    if body.full_name is not None:
        name = body.full_name.strip()
        if not name:
            raise FieldError("full_name", "نام نمی‌تواند خالی باشد.")
        person.full_name = name

    person.phone, person.phone_raw = _valid_phone(body.phone)
    await _phone_free(session, person.phone, person.id)

    person.bank_account = _bank(body.bank_account)

    contacts = [c for c in body.contacts if c.handle.strip()]
    if sum(c.is_default for c in contacts) > 1:
        raise FieldError("contacts", "فقط یک راه ارتباطی می‌تواند پیش‌فرض باشد.")
    if contacts and not any(c.is_default for c in contacts):
        contacts[0] = contacts[0].model_copy(update={"is_default": True})
    await session.execute(delete(PersonContact).where(PersonContact.person_id == person.id))
    for c in contacts:
        session.add(
            PersonContact(
                person_id=person.id,
                platform=c.platform,
                handle=c.handle.strip(),
                is_default=c.is_default,
            )
        )
    await session.flush()

    after = _state(person, await get_profile(session, person))
    await record(
        session,
        user,
        action="update",
        entity="person",
        entity_id=person.id,
        before=before,
        after=after,
    )
    await session.commit()
    return person
