"""Member list import: fills the registry, keeps people matched by name across Excel re-imports."""

from __future__ import annotations

from pathlib import Path

import openpyxl
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.config import settings
from app.importer.members import _same_person, _undouble, apply_members, phones, read_members
from app.importer.runner import parse_workbook
from app.importer.writer import write_parse_result

pytestmark = pytest.mark.integration

HEADER = ["نام", "نام خانوادگی", "نام و نام خانوادگی", "کدملی", "شماره تماس", "پیامرسان",
          "شماره کارت", "شماره شبا", "معرف"]  # fmt: skip


def test_undouble_and_same_person() -> None:
    assert _undouble("مریم طاهری طاهری") == "مریم طاهری"
    assert _undouble("حامد آهنگر اهنگر") == "حامد آهنگر"
    assert _same_person("ابوالفضل حسینی", "سیدابوالفضل حسینی") is False  # «سید» glued: kept apart
    assert _same_person("سید محمد علوی", "سید محمد هادی پور") is False
    assert _same_person("علی توحیدی", "علی توحیدی فشتمی") is True


def test_phones_splits_glued_numbers() -> None:
    assert phones("0912 123 4567") == ["+989121234567"]
    assert phones("0912123456709351234567") == ["+989121234567", "+989351234567"]
    assert phones("123") == []


async def _run(path: Path) -> None:
    engine = create_async_engine(str(settings.database_url))
    async with async_sessionmaker(engine, expire_on_commit=False)() as session:
        await apply_members(session, read_members(path))
        await session.commit()
    await engine.dispose()


@pytest.mark.asyncio
async def test_member_list_fills_registry_and_survives_reimport(
    seeded_client: AsyncClient, sample_xlsm_path: Path, tmp_path: Path
) -> None:
    existing = (await seeded_client.get("/api/persons?page_size=1")).json()["items"][0]
    name = existing["full_name"]
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(HEADER)
    ws.append(["علی", "نمونه", name, 12345678, 9121234567, "بله, ایتا", "6037 9911 2233 4455",
               "IR12 0170 0000 0012 3456 7890 01", "x"])  # fmt: skip
    ws.append([None, None, name, None, "09351234567", None, "6219861012345678", None, None])
    # Same national code, surname typed twice: the same member.
    ws.append(["رضا", "تکراری", None, "0011112222", None, None, None, None, None])
    ws.append(["رضا تکراری", "تکراری", None, "11112222", None, None, None, None, None])
    ws.append(["رضا", "دیگری", None, "0011112222", None, None, None, None, None])
    ws.append([None, None, "عضو تازه", None, "09121234567", "تلگرام", None, None, None])
    ws.append(["فقط", "نام", None, None, None, None, None, None, None])
    path = tmp_path / "list.xlsx"
    wb.save(path)
    await _run(path)

    d = (await seeded_client.get(f"/api/persons/{existing['id']}")).json()
    assert d["person"]["phone"] == "+989121234567"
    assert d["person"]["national_code"] == "0012345678"
    assert d["profile"]["first_name"] == "علی"
    assert d["profile"]["card_numbers"] == ["6037991122334455", "6219861012345678"]
    assert d["profile"]["ibans"] == ["IR120170000000123456789001"]
    got = {(c["platform"], c["handle"], c["is_default"]) for c in d["profile"]["contacts"]}
    assert got == {
        ("bale", "09121234567", True),
        ("eitaa", "09121234567", False),
        ("phone", "09351234567", False),
    }

    # The shared phone stays with the first owner; the new member gets it as a contact.
    new = (await seeded_client.get("/api/persons?q=عضو تازه")).json()["items"][0]
    nd = (await seeded_client.get(f"/api/persons/{new['id']}")).json()
    assert nd["person"]["phone"].startswith("+0__")
    assert nd["profile"]["contacts"] == [
        {"platform": "phone", "handle": "09121234567", "is_default": False}
    ]
    assert (await seeded_client.get("/api/persons?q=فقط نام")).json()["total"] == 1
    found = (await seeded_client.get("/api/persons?q=رضا")).json()["items"]
    codes = {p["full_name"]: p["national_code"] for p in found}
    assert [n for n in codes if "تکراری" in n] == ["رضا تکراری"]
    assert codes["رضا تکراری"] == "0011112222"
    assert codes["رضا دیگری"] is None  # same code, different person: not given twice

    # Second run changes nothing; an Excel re-import finds the person by name.
    await _run(path)
    engine = create_async_engine(str(settings.database_url))
    async with async_sessionmaker(engine, expire_on_commit=False)() as session:
        await write_parse_result(
            session,
            source_path=sample_xlsm_path,
            sha256="8" * 64,
            duration_ms=0,
            result=parse_workbook(sample_xlsm_path),
        )
    await engine.dispose()
    same = (await seeded_client.get(f"/api/persons?q={name}&page_size=50")).json()["items"]
    assert [p["id"] for p in same if p["full_name"] == name] == [existing["id"]]
    again = (await seeded_client.get(f"/api/persons/{existing['id']}")).json()
    assert len(again["profile"]["contacts"]) == 3


@pytest.mark.asyncio
async def test_rename_keeps_old_name_for_import(seeded_client: AsyncClient) -> None:
    p = (await seeded_client.get("/api/persons?page_size=1")).json()["items"][0]
    r = await seeded_client.patch(
        f"/api/persons/{p['id']}",
        json={"full_name": "نام تازه", "phone": "09120000001", "national_code": "123"},
    )
    assert r.status_code == 422
    assert r.json()["detail"][0]["loc"] == ["body", "national_code"]
    r = await seeded_client.patch(
        f"/api/persons/{p['id']}",
        json={
            "full_name": "نام تازه",
            "phone": "09120000001",
            "ibans": ["120170000000123456789001"],
        },
    )
    assert r.status_code == 200, r.text
    assert r.json()["profile"]["ibans"] == ["IR120170000000123456789001"]
    aliases = (await seeded_client.get(f"/api/audit?entity=person&entity_id={p['id']}")).json()
    assert aliases[0]["before"]["full_name"] == p["full_name"]
