"""Integration tests for ``GET /api/loans*`` against the seeded sample."""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.config import settings
from app.importer.runner import run_import
from app.main import app

pytestmark = pytest.mark.integration

_WIPE_TABLES = (
    "data_issue",
    "installment",
    "loan_party",
    "loan",
    "import",
    "person_guarantor",
    "person",
)


@pytest.fixture
async def seeded_client(sample_xlsm_path: Path) -> AsyncIterator[AsyncClient]:
    engine = create_async_engine(str(settings.database_url))
    sessionmaker = async_sessionmaker(engine, expire_on_commit=False)

    async def wipe() -> None:
        async with engine.begin() as conn:
            for t in _WIPE_TABLES:
                await conn.exec_driver_sql(f"DELETE FROM {t}")

    await wipe()
    async with sessionmaker() as session:
        await run_import(session, sample_xlsm_path)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    await wipe()
    await engine.dispose()


# --- list ---


@pytest.mark.asyncio
async def test_loans_list_default_returns_all_9(seeded_client: AsyncClient) -> None:
    r = await seeded_client.get("/api/loans")
    body = r.json()
    assert r.status_code == 200, r.text
    assert body["total"] == 9


@pytest.mark.asyncio
async def test_loans_list_year_filter(seeded_client: AsyncClient) -> None:
    r1404 = (await seeded_client.get("/api/loans?year=1404")).json()
    r1405 = (await seeded_client.get("/api/loans?year=1405")).json()
    assert r1404["total"] == 5
    assert r1405["total"] == 4
    assert {ln["persian_year"] for ln in r1404["items"]} == {1404}
    assert {ln["persian_year"] for ln in r1405["items"]} == {1405}


@pytest.mark.asyncio
async def test_loans_list_status_filter(seeded_client: AsyncClient) -> None:
    active = (await seeded_client.get("/api/loans?status=active")).json()
    settled = (await seeded_client.get("/api/loans?status=settled")).json()
    assert active["total"] + settled["total"] == 9
    assert all(ln["status"] == "active" for ln in active["items"])
    assert all(ln["status"] == "settled" for ln in settled["items"])


@pytest.mark.asyncio
async def test_loans_list_q_loan_number(seeded_client: AsyncClient) -> None:
    r = (await seeded_client.get("/api/loans?q=1500")).json()
    assert r["total"] == 1
    assert r["items"][0]["loan_number"] == "1500"


# --- detail ---


@pytest.mark.asyncio
async def test_loan_1500_detail_has_1_borrower_and_3_lenders(
    seeded_client: AsyncClient,
) -> None:
    listing = (await seeded_client.get("/api/loans?q=1500")).json()
    loan_id = listing["items"][0]["id"]
    r = await seeded_client.get(f"/api/loans/{loan_id}")
    assert r.status_code == 200, r.text
    body = r.json()

    # Required keys (DESIGN.md §5.2)
    assert set(body) == {"loan", "topic", "guarantor", "borrowers", "lenders", "totals"}
    assert body["loan"]["loan_number"] == "1500"
    assert body["topic"]["name"] == "درمان"

    # Phase 1 contract: exactly one borrower
    assert len(body["borrowers"]) == 1
    assert body["borrowers"][0]["person"]["full_name"] == "نفر 1"
    assert float(body["borrowers"][0]["amount"]) == 20

    # 3 lenders summing to 20
    lenders = body["lenders"]
    assert [ln["person"]["full_name"] for ln in lenders] == ["نفر 2", "نفر 3", "نفر 4"]
    assert [float(ln["amount"]) for ln in lenders] == [3, 7, 10]
    assert sum(float(ln["amount"]) for ln in lenders) == 20

    # نفر 2 paid 1 installment of 3 → her party.paid = 3 and remaining = 0.
    n2 = next(ln for ln in lenders if ln["person"]["full_name"] == "نفر 2")
    assert float(n2["paid"]) == 3
    assert float(n2["remaining"]) == 0
    assert len(n2["installments"]) == 1
    assert n2["installments"][0]["status"] == "paid"

    # Totals reconcile
    t = body["totals"]
    assert float(t["total"]) == 20
    assert float(t["paid"]) + float(t["remaining"]) == 20


@pytest.mark.asyncio
async def test_loan_detail_404(seeded_client: AsyncClient) -> None:
    r = await seeded_client.get("/api/loans/999999")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_loans_sort_by_loan_number(seeded_client: AsyncClient) -> None:
    asc = (await seeded_client.get("/api/loans?sort=loan_number&sort_dir=asc")).json()
    desc = (await seeded_client.get("/api/loans?sort=loan_number&sort_dir=desc")).json()

    def nums(body: dict) -> list[int]:
        return [int(it["loan_number"]) for it in body["items"]]

    asc_nums = nums(asc)
    assert asc_nums == sorted(asc_nums), "ascending must be numeric, not lexicographic"
    assert nums(desc) == sorted(nums(desc), reverse=True)
    # Same set both ways, just reordered.
    assert set(asc_nums) == set(nums(desc))


@pytest.mark.asyncio
async def test_loans_sort_by_total_desc(seeded_client: AsyncClient) -> None:
    body = (await seeded_client.get("/api/loans?sort=total&sort_dir=desc")).json()
    totals = [float(it["total"]) for it in body["items"]]
    assert totals == sorted(totals, reverse=True)
