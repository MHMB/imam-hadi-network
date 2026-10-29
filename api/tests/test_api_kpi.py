"""Integration test for ``GET /api/kpi`` against the seeded sample data."""

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
    """Wipe importer-managed tables, run import on sample, yield an HTTP client."""
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


@pytest.mark.asyncio
async def test_kpi_shape_and_counts(seeded_client: AsyncClient) -> None:
    r = await seeded_client.get("/api/kpi")
    assert r.status_code == 200, r.text
    body = r.json()
    # Required keys
    assert set(body) == {
        "persons_total",
        "loans_total",
        "loans_active",
        "loans_settled",
        "total_amount",
        "outstanding_total",
        "overdue_installments",
        "overdue_loans",
        "overdue_amount",
        "by_year",
    }

    # Sample has 21 persons + 9 loans split across 1404 (5) and 1405 (4).
    assert body["persons_total"] == 21
    assert body["loans_total"] == 9
    assert body["loans_active"] + body["loans_settled"] == 9

    years = {y["year"] for y in body["by_year"]}
    assert years == {1404, 1405}
    counts = {y["year"]: y["loan_count"] for y in body["by_year"]}
    assert counts == {1404: 5, 1405: 4}


@pytest.mark.asyncio
async def test_kpi_outstanding_consistency(seeded_client: AsyncClient) -> None:
    r = await seeded_client.get("/api/kpi")
    body = r.json()
    # outstanding_total must equal sum of per-year outstanding.
    by_year_sum = sum(float(y["outstanding"]) for y in body["by_year"])
    assert float(body["outstanding_total"]) == pytest.approx(by_year_sum)


@pytest.mark.asyncio
async def test_kpi_settled_matches_loan_list(seeded_client: AsyncClient) -> None:
    body = (await seeded_client.get("/api/kpi")).json()
    settled = (await seeded_client.get("/api/loans", params={"status": "settled"})).json()
    assert body["loans_settled"] == settled["total"]


@pytest.mark.asyncio
async def test_kpi_overdue_matches_overdue_list(seeded_client: AsyncClient) -> None:
    body = (await seeded_client.get("/api/kpi")).json()
    items = (
        await seeded_client.get("/api/installments/overdue", params={"page_size": 500})
    ).json()["items"]
    assert body["overdue_installments"] == len(items)
    assert body["overdue_loans"] == len({i["loan_id"] for i in items})
    assert float(body["overdue_amount"]) == pytest.approx(sum(float(i["amount"]) for i in items))
    assert body["overdue_loans"] <= body["loans_active"]
