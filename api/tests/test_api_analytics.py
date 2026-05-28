"""Integration tests for ``GET /api/analytics/monthly``."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import date
from pathlib import Path

import jdatetime
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.config import settings
from app.importer.runner import run_import
from app.main import app
from app.services.analytics import previous_jalali_month

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


# --- pure unit ---


def test_previous_jalali_month_simple() -> None:
    assert previous_jalali_month(jdatetime.date(1405, 5, 10)) == (1405, 4)


def test_previous_jalali_month_crosses_year() -> None:
    assert previous_jalali_month(jdatetime.date(1405, 1, 5)) == (1404, 12)


# --- integration ---


@pytest.mark.asyncio
async def test_monthly_shape_default(seeded_client: AsyncClient) -> None:
    r = await seeded_client.get("/api/analytics/monthly")
    assert r.status_code == 200, r.text
    body = r.json()
    assert set(body) == {
        "period",
        "new_loans",
        "installments_due",
        "new_loans_by_topic",
        "top_borrowers",
        "top_lenders",
    }
    assert set(body["period"]) == {"persian_year", "persian_month", "label_fa"}
    assert 1 <= body["period"]["persian_month"] <= 12

    # Default period = previous Jalali month vs today.
    today_j = jdatetime.date.fromgregorian(date=date.today())
    expected_year, expected_month = previous_jalali_month(today_j)
    assert (
        body["period"]["persian_year"],
        body["period"]["persian_month"],
    ) == (expected_year, expected_month)


@pytest.mark.asyncio
async def test_monthly_explicit_year_month(seeded_client: AsyncClient) -> None:
    # Sample data has installments due in many Jalali 1404 months; pick 1404/06.
    r = await seeded_client.get("/api/analytics/monthly?year=1404&month=6")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["period"]["persian_year"] == 1404
    assert body["period"]["persian_month"] == 6

    # Sample loan 1500 lender نفر 2 has installment due 1404/06/15.
    by_day = {d["day"]: d for d in body["installments_due"]["by_day"]}
    assert 15 in by_day
    # That installment is paid (green) per sample → paid_amount > 0 on day 15.
    assert float(by_day[15]["paid_amount"]) > 0


@pytest.mark.asyncio
async def test_payment_rate_zero_when_no_installments(seeded_client: AsyncClient) -> None:
    # Pick a month with no installments due (1406/02 — past last scheduled).
    body = (await seeded_client.get("/api/analytics/monthly?year=1410&month=12")).json()
    assert body["installments_due"]["count"] == 0
    assert body["installments_due"]["payment_rate_pct"] == 0


@pytest.mark.asyncio
async def test_monthly_topic_breakdown_nonempty_for_import_month(
    seeded_client: AsyncClient,
) -> None:
    """New-loans grouping uses loan.created_at (= import time).  The import
    just ran in the test fixture, so the *current* Jalali month should hold
    all 9 sample loans grouped by their topics."""
    today_j = jdatetime.date.fromgregorian(date=date.today())
    body = (
        await seeded_client.get(f"/api/analytics/monthly?year={today_j.year}&month={today_j.month}")
    ).json()
    assert body["new_loans"]["count"] == 9
    # Total of all loans in the sample = 148M (per /api/kpi).
    assert float(body["new_loans"]["total_amount"]) == 148

    topic_count_sum = sum(t["count"] for t in body["new_loans_by_topic"])
    assert topic_count_sum == 9

    # Top borrowers + lenders capped at 5 each.
    assert len(body["top_borrowers"]) <= 5
    assert len(body["top_lenders"]) <= 5


@pytest.mark.asyncio
async def test_installments_due_paid_unpaid_split_sums_to_total(
    seeded_client: AsyncClient,
) -> None:
    body = (await seeded_client.get("/api/analytics/monthly?year=1404&month=6")).json()
    summary = body["installments_due"]
    assert float(summary["amount_paid"]) + float(summary["amount_unpaid"]) == float(
        summary["amount_total"]
    )
    if float(summary["amount_total"]) > 0:
        expected_rate = float(summary["amount_paid"]) / float(summary["amount_total"]) * 100
        assert abs(summary["payment_rate_pct"] - round(expected_rate, 2)) < 0.01
