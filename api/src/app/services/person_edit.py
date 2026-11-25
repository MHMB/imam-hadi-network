"""Editing a person's profile: name, phone (required), bank account, contacts."""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import FieldError
from app.importer.names import resolve_key
from app.importer.phone import canonicalize
from app.models import AppUser, Person, PersonAlias, PersonContact
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
        card_numbers=person.card_numbers,
        ibans=person.ibans,
        first_name=person.first_name,
        last_name=person.last_name,
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


def _digits(value: str) -> str:
    return re.sub(r"[\s\-]", "", value.translate(_PERSIAN_DIGITS)).upper()


def _each(clean: Callable[[str], str | None], values: list[str]) -> list[str]:
    out: list[str] = []
    for v in values:
        if (c := clean(v)) and c not in out:
            out.append(c)
    return out


def clean_card(value: str | None) -> str | None:
    if value is None or not value.strip():
        return None
    card = _digits(value)
    if not re.fullmatch(r"\d{16}", card):
        raise FieldError("card_numbers", "شماره کارت باید ۱۶ رقم باشد.")
    return card


def clean_iban(value: str | None) -> str | None:
    if value is None or not value.strip():
        return None
    iban = _digits(value)
    iban = iban if iban.startswith("IR") else f"IR{iban}"
    if not re.fullmatch(r"IR\d{24}", iban):
        raise FieldError("ibans", "شماره شبا باید IR و ۲۴ رقم باشد.")
    return iban


def clean_national_code(value: str | None) -> str | None:
    """10 digits; Excel drops leading zeros, so 8–9 digit codes are zero-padded."""
    if value is None or not value.strip():
        return None
    code = _digits(value)
    if re.fullmatch(r"\d{8,9}", code):
        code = code.zfill(10)
    if not re.fullmatch(r"\d{10}", code):
        raise FieldError("national_code", "کد ملی باید ۱۰ رقم باشد.")
    return code


async def national_code_owner(
    session: AsyncSession, code: str, person_id: int | None
) -> str | None:
    """Name of another person already holding this national code, if any."""
    return (
        await session.execute(
            select(Person.full_name).where(
                Person.national_code == code, Person.id != (person_id or 0)
            )
        )
    ).scalar_one_or_none()


async def remember_old_name(session: AsyncSession, person: Person, old_name: str) -> None:
    """After a rename, keep the old spelling mapped here so Excel imports still find them."""
    key = resolve_key(old_name)
    if key and key != resolve_key(person.full_name):
        await session.execute(
            insert(PersonAlias)
            .values(name_key=key, name=old_name, person_id=person.id)
            .on_conflict_do_update(
                index_elements=["name_key"],
                set_={"name": old_name},
                # Never take over a name another person's alias already holds.
                where=PersonAlias.person_id == person.id,
            )
        )


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
        old_name, person.full_name = person.full_name, name
        await remember_old_name(session, person, old_name)

    person.phone, person.phone_raw = _valid_phone(body.phone)
    await _phone_free(session, person.phone, person.id)

    person.bank_account = _bank(body.bank_account)
    person.card_numbers = _each(clean_card, body.card_numbers)
    person.ibans = _each(clean_iban, body.ibans)
    person.first_name = (body.first_name or "").strip() or None
    person.last_name = (body.last_name or "").strip() or None
    person.national_code = clean_national_code(body.national_code)
    if person.national_code and (
        owner := await national_code_owner(session, person.national_code, person.id)
    ):
        raise FieldError(
            "national_code", f"این کد ملی قبلاً برای «{owner}» ثبت شده است.", code="duplicate"
        )

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
