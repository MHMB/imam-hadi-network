"""Import a member list into the person registry.

Usage::

    python -m app.importer.members /uploads/list.xlsx [--dry-run]

One row per person: «نام», «نام خانوادگی», «نام و نام خانوادگی», «کدملی»,
«شماره تماس», «پیامرسان», «شماره کارت», «شماره شبا».  «معرف» columns
are ignored.

- Rows are matched to people by name (merged-name aliases included); rows
  repeating one name are one person.  Unknown names become new persons.
- Only empty fields are filled: anything already set in the app wins.
- A phone already used by someone else (family members share numbers) is
  kept as a «تلفن» contact instead of the person's main phone.
- Every person touched gets one audit row.  Conflicts are reported, not
  guessed: the first value wins, the rest are listed.
"""

from __future__ import annotations

import asyncio
import re
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Annotated

import openpyxl
import typer
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import FieldError
from app.importer.names import normalize_display, placeholder_phone, resolve_key
from app.importer.phone import canonicalize
from app.importer.runner import open_session
from app.models import AppUser, Person, PersonAlias, PersonContact
from app.models.enums import Platform
from app.services.audit import record, snapshot
from app.services.person_edit import clean_card, clean_iban, clean_national_code

HEADERS = {
    "first": "نام",
    "last": "نام خانوادگی",
    "full": "نام و نام خانوادگی",
    "nid": "کدملی",
    "phone": "شماره تماس",
    "msgr": "پیامرسان",
    "card": "شماره کارت",
    "iban": "شماره شبا",
}
MESSENGERS = {
    "بله": Platform.bale,
    "ایتا": Platform.eitaa,
    "تلگرام": Platform.telegram,
    "واتساپ": Platform.whatsapp,
    "روبیکا": Platform.rubika,
}
IMPORT_USER = "member-import"
PLACEHOLDER = "+0__"  # see app.importer.names.placeholder_phone


@dataclass
class Member:
    """All rows of one person, in sheet order: same name, or same national code."""

    name: str
    rows: list[dict[str, str]] = field(default_factory=list)
    other_names: list[str] = field(default_factory=list)

    def values(self, f: str) -> list[str]:
        out: list[str] = []
        for r in self.rows:
            if r[f] and r[f] not in out:
                out.append(r[f])
        return out


@dataclass
class Report:
    matched: int = 0
    created: int = 0
    updated: int = 0
    problems: list[str] = field(default_factory=list)


def _cell(v: object) -> str:
    if isinstance(v, float) and v.is_integer():
        v = int(v)
    return normalize_display(v)


def _fold(word: str) -> str:
    return word.replace("آ", "ا").replace("ئ", "ی").replace("ي", "ی").replace("ك", "ک")


def _undouble(name: str) -> str:
    """«مریم طاهری طاهری» → «مریم طاهری»: the surname cell repeated inside the first-name cell."""
    out: list[str] = []
    for w in name.split():
        if not out or _fold(w) != _fold(out[-1]):
            out.append(w)
    return " ".join(out)


def _same_person(a: str, b: str) -> bool:
    """Same first name and a shared surname word (titles like «سید» ignored)."""
    words = [[_fold(w) for w in n.split() if w not in ("سید", "سیده")] for n in (a, b)]
    return (
        bool(words[0] and words[1])
        and words[0][0] == words[1][0]
        and bool(set(words[0][1:]) & set(words[1][1:]))
    )


def _code(v: str) -> str | None:
    try:
        return clean_national_code(v)
    except FieldError:
        return None


def read_members(path: Path) -> list[Member]:
    ws = openpyxl.load_workbook(path, read_only=True, data_only=True).worksheets[0]
    rows = ws.iter_rows(values_only=True)
    header = [_cell(h) for h in next(rows)]
    col = {f: header.index(h) for f, h in HEADERS.items() if h in header}
    if "full" not in col and not {"first", "last"} <= col.keys():
        raise ValueError("ستون «نام و نام خانوادگی» پیدا نشد.")
    members: dict[str, Member] = {}
    for raw in rows:
        r = {f: _cell(raw[i]) if i < len(raw) else "" for f, i in col.items()}
        for f in HEADERS:
            r.setdefault(f, "")
        name = _undouble(r["full"] or f"{r['first']} {r['last']}".strip())
        key = resolve_key(name)
        if key:
            members.setdefault(key, Member(name)).rows.append(r)

    # One national code under two spellings of one name is one person.
    by_code: dict[str, Member] = {}
    out: list[Member] = []
    for m in members.values():
        first = next((by_code[c] for v in m.values("nid") if (c := _code(v)) in by_code), None)
        if first is not None and _same_person(first.name, m.name):
            first.rows += m.rows
            first.other_names += [m.name, *m.other_names]
            continue
        out.append(m)
        for v in m.values("nid"):
            if c := _code(v):
                by_code.setdefault(c, m)
    return out


def phones(text: str) -> list[str]:
    """Every valid number in a cell, also two numbers glued into one."""
    digits = re.sub(r"\D", "", text.translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")))
    found = re.findall(r"(?:0098|98|0)?9\d{9}", digits) or [digits]
    out: list[str] = []
    for p in found:
        c = canonicalize(p)
        if c.canonical and c.issue is None and c.canonical not in out:
            out.append(c.canonical)
    return out


def _local(phone: str) -> str:
    return "0" + phone[3:] if phone.startswith("+98") else phone


def _valid(m: Member, f: str, clean: Callable[[str], str | None], report: Report) -> list[str]:
    good: list[str] = []
    for v in m.values(f):
        try:
            c = clean(v)
        except FieldError:
            report.problems.append(f"«{m.name}»: {HEADERS[f]} نامعتبر ({v})")
            continue
        if c and c not in good:
            good.append(c)
    return good


@dataclass
class Registry:
    """What is already taken, so one run never assigns a phone or code twice."""

    by_key: dict[str, Person]
    phone_owner: dict[str, str]
    code_owner: dict[str, str]
    contacts: dict[int, set[tuple[str, str]]]
    defaults: set[int]

    @classmethod
    async def load(cls, session: AsyncSession) -> Registry:
        people = list((await session.execute(select(Person))).scalars())
        by_key = {resolve_key(p.full_name): p for p in people}
        by_id = {p.id: p for p in people}
        aliases = await session.execute(select(PersonAlias.name_key, PersonAlias.person_id))
        for key, pid in aliases.all():
            if pid in by_id:
                by_key[str(key)] = by_id[pid]
        reg = cls(
            by_key=by_key,
            phone_owner={p.phone: p.full_name for p in people},
            code_owner={p.national_code: p.full_name for p in people if p.national_code},
            contacts=defaultdict(set),
            defaults=set(),
        )
        for c in (await session.execute(select(PersonContact))).scalars():
            reg.contacts[c.person_id].add((c.platform.value, c.handle))
            if c.is_default:
                reg.defaults.add(c.person_id)
        return reg

    def free_phone(self, nums: list[str]) -> str | None:
        return next((p for p in nums if p not in self.phone_owner), None)


def _fill_fields(person: Person, m: Member, nums: list[str], reg: Registry, report: Report) -> None:
    """Fill empty profile fields from the member's rows."""
    if person.phone.startswith(PLACEHOLDER) and (main := reg.free_phone(nums)):
        person.phone, person.phone_raw = main, _local(main)
        reg.phone_owner[main] = person.full_name
    if not person.first_name and (first := m.values("first")):
        person.first_name = first[-1][:100]
    if not person.last_name and (last := m.values("last")):
        person.last_name = last[-1][:100]
    codes = _valid(m, "nid", clean_national_code, report)
    if len(codes) > 1:
        report.problems.append(f"«{m.name}»: چند کد ملی ({'، '.join(codes)}) — اولی ثبت شد")
    if not person.national_code and (code := next(iter(codes), None)):
        if code in reg.code_owner:
            report.problems.append(
                f"«{m.name}»: کد ملی {code} برای «{reg.code_owner[code]}» ثبت است"
            )
        else:
            person.national_code = code
            reg.code_owner[code] = person.full_name
    cards = _valid(m, "card", clean_card, report)
    person.card_numbers = list(dict.fromkeys([*person.card_numbers, *cards]))
    ibans = _valid(m, "iban", clean_iban, report)
    person.ibans = list(dict.fromkeys([*person.ibans, *ibans]))
    if msgr := m.values("msgr"):
        person.messenger = person.messenger or "، ".join(msgr)[:120]


def _add_contacts(
    session: AsyncSession, person: Person, m: Member, nums: list[str], reg: Registry
) -> bool:
    """Other numbers as «تلفن»; each messenger named on the main number."""
    wanted = [(Platform.phone, _local(p)) for p in nums if p != person.phone]
    if not person.phone.startswith(PLACEHOLDER):
        tokens = {t for v in m.values("msgr") for t in re.split(r"[,،/\s]+", v)}
        wanted += [(pl, _local(person.phone)) for t, pl in MESSENGERS.items() if t in tokens]
    added = False
    for platform, handle in wanted:
        if (platform.value, handle) in reg.contacts[person.id]:
            continue
        is_default = person.id not in reg.defaults and platform is not Platform.phone
        session.add(
            PersonContact(
                person_id=person.id, platform=platform, handle=handle, is_default=is_default
            )
        )
        if is_default:
            reg.defaults.add(person.id)
        reg.contacts[person.id].add((platform.value, handle))
        added = True
    return added


async def _remember_names(
    session: AsyncSession, person: Person, names: list[str], reg: Registry
) -> None:
    """Other spellings of this member map to them on future imports."""
    for name in names:
        key = resolve_key(name)
        if key in reg.by_key:
            continue
        await session.execute(
            insert(PersonAlias).values(name_key=key, name=name, person_id=person.id)
        )
        reg.by_key[key] = person


async def apply_members(session: AsyncSession, members: list[Member]) -> Report:
    report = Report()
    await session.execute(
        insert(AppUser)
        .values(username=IMPORT_USER)
        .on_conflict_do_nothing(index_elements=["username"])
    )
    user = (
        await session.execute(select(AppUser).where(AppUser.username == IMPORT_USER))
    ).scalar_one()
    reg = await Registry.load(session)

    for m in members:
        nums = [p for v in m.values("phone") for p in phones(v)]
        names = [m.name, *m.other_names]
        found = {
            reg.by_key[k].id: reg.by_key[k] for n in names if (k := resolve_key(n)) in reg.by_key
        }
        person = next(iter(found.values()), None)
        if len(found) > 1:
            report.problems.append(
                "یک کد ملی برای چند نفر سامانه: "
                + "، ".join(f"«{p.full_name}» #{p.id}" for p in found.values())
            )
        before = None if person is None else snapshot(person)
        if person is None:
            person = Person(
                phone=reg.free_phone(nums) or placeholder_phone(m.name), full_name=m.name
            )
            session.add(person)
            await session.flush()
            reg.by_key[resolve_key(m.name)] = person
            reg.phone_owner[person.phone] = person.full_name
            report.created += 1
        else:
            report.matched += 1

        await _remember_names(session, person, m.other_names, reg)
        _fill_fields(person, m, nums, reg, report)
        added = _add_contacts(session, person, m, nums, reg)
        await session.flush()
        after = snapshot(person)
        if before != after or added:
            report.updated += before is not None
            await record(
                session,
                user,
                action="import_members",
                entity="person",
                entity_id=person.id,
                before=before,
                after=after,
            )
    return report


app = typer.Typer(no_args_is_help=True, add_completion=False)


@app.command()
def run(
    file: Annotated[Path, typer.Argument(exists=True, dir_okay=False, readable=True)],
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Report only, write nothing.")] = False,
) -> None:
    """Fill the person registry from a member list."""

    async def main() -> Report:
        async with open_session() as session:
            report = await apply_members(session, read_members(file))
            if dry_run:
                await session.rollback()
            else:
                await session.commit()
            return report

    r = asyncio.run(main())
    print(
        f"{'DRY RUN: ' if dry_run else ''}matched={r.matched} created={r.created} updated={r.updated} problems={len(r.problems)}"
    )
    for p in r.problems:
        print("  -", p)


if __name__ == "__main__":
    app()
