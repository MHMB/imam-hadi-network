"""Integration tests for ``GET /api/persons*`` against the seeded sample."""

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


# --- list / search ---


@pytest.mark.asyncio
async def test_persons_list_shape_and_pagination(seeded_client: AsyncClient) -> None:
    r = await seeded_client.get("/api/persons?page_size=5")
    assert r.status_code == 200, r.text
    body = r.json()
    assert set(body) == {"items", "total", "page", "page_size"}
    assert body["total"] == 21
    assert body["page"] == 1
    assert body["page_size"] == 5
    assert len(body["items"]) == 5


@pytest.mark.asyncio
async def test_persons_search_persian_fuzzy(seeded_client: AsyncClient) -> None:
    # Exact match
    r = await seeded_client.get("/api/persons?q=نفر 1")
    body = r.json()
    assert any(p["full_name"] == "نفر 1" for p in body["items"])

    # Arabic ye/kaf should still hit Persian record once a real production
    # name uses Arabic forms; here we just confirm normalisation doesn't
    # break the simple case.
    r = await seeded_client.get("/api/persons?q=نفر")
    body = r.json()
    assert body["total"] >= 1


@pytest.mark.asyncio
async def test_persons_list_rollups_for_n2(seeded_client: AsyncClient) -> None:
    """نفر 2 lent on loans 1500 (3) + 1504 (5) = 8; borrowed 0."""
    r = await seeded_client.get("/api/persons?q=نفر 2")
    body = r.json()
    n2 = next(p for p in body["items"] if p["full_name"] == "نفر 2")
    assert float(n2["total_lent"]) == 8
    assert float(n2["total_borrowed"]) == 0
    # Rollup must be self-consistent: 0 ≤ outstanding ≤ total_lent
    outstanding = float(n2["outstanding_receivable"])
    assert 0 <= outstanding <= float(n2["total_lent"])
    # net_capital = receivable - debt
    assert float(n2["net_capital"]) == outstanding - float(n2["outstanding_debt"])


# --- detail ---


@pytest.mark.asyncio
async def test_person_detail_includes_per_year_and_lifetime(
    seeded_client: AsyncClient,
) -> None:
    # Resolve نفر 2's id first
    list_r = (await seeded_client.get("/api/persons?q=نفر 2")).json()
    n2 = next(p for p in list_r["items"] if p["full_name"] == "نفر 2")
    r = await seeded_client.get(f"/api/persons/{n2['id']}")
    assert r.status_code == 200, r.text
    body = r.json()
    assert set(body) == {"person", "guarantors", "by_year", "lifetime", "upcoming", "overdue"}
    assert body["person"]["full_name"] == "نفر 2"
    # 1404 only — نفر 2 doesn't appear as lender in 1405 sample loans.
    years = {y["year"] for y in body["by_year"]}
    assert 1404 in years
    y1404 = next(y for y in body["by_year"] if y["year"] == 1404)
    assert y1404["as_lender_parties"] >= 2  # نفر 2 appears on 1500 + 1504
    assert float(y1404["as_lender_total"]) == 8


@pytest.mark.asyncio
async def test_person_detail_404(seeded_client: AsyncClient) -> None:
    r = await seeded_client.get("/api/persons/999999")
    assert r.status_code == 404
