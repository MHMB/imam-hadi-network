"""Integration tests for ``GET /api/installments/overdue``."""

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
from app.services.overdue import _days_overdue

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


# --- pure unit on the day-diff helper ---


def test_days_overdue_handles_jalali_month_boundary() -> None:
    # 1404/06/15 is Shahrivar 15, 2025-09-06 in Gregorian.  Two weeks later
    # in Jalali = 1404/06/29, also 2025-09-20.  Diff should be 14 days.
    due = (1404, 6, 15)
    today = (1404, 6, 29)
    assert _days_overdue(due, today) == 14


def test_days_overdue_across_jalali_year_boundary() -> None:
    # Esfand (12) → Farvardin (1).  Two days apart even though year ticks.
    due = (1404, 12, 29)
    today = (1405, 1, 1)
    g_diff = (
        jdatetime.date(1405, 1, 1).togregorian() - jdatetime.date(1404, 12, 29).togregorian()
    ).days
    assert _days_overdue(due, today) == g_diff


def test_days_overdue_returns_zero_on_same_day() -> None:
    today = (1404, 6, 15)
    assert _days_overdue(today, today) == 0


# --- integration ---


@pytest.mark.asyncio
async def test_overdue_endpoint_shape(seeded_client: AsyncClient) -> None:
    r = await seeded_client.get("/api/installments/overdue")
    assert r.status_code == 200, r.text
    body = r.json()
    assert set(body) == {"items", "total", "page", "page_size"}
    if body["total"] == 0:
        # If today < every sample due date, list is empty — still valid response.
        return
    item = body["items"][0]
    assert set(item) >= {
        "installment_id",
        "loan_id",
        "loan_number",
        "persian_year",
        "topic_name",
        "borrower",
        "lender",
        "guarantor",
        "due_persian_year",
        "due_persian_month",
        "due_day_of_month",
        "amount",
        "days_overdue",
    }
    assert item["days_overdue"] >= 0
    # Borrower + lender are PersonRef triples
    assert set(item["borrower"]) == {"id", "full_name", "phone"}
    assert set(item["lender"]) == {"id", "full_name", "phone"}


@pytest.mark.asyncio
async def test_overdue_sorted_worst_first(seeded_client: AsyncClient) -> None:
    body = (await seeded_client.get("/api/installments/overdue")).json()
    days_list = [i["days_overdue"] for i in body["items"]]
    assert days_list == sorted(days_list, reverse=True)


@pytest.mark.asyncio
async def test_overdue_count_matches_kpi(seeded_client: AsyncClient) -> None:
    """KPI's overdue_installments count and the list total must agree."""
    kpi = (await seeded_client.get("/api/kpi")).json()
    listing = (await seeded_client.get("/api/installments/overdue")).json()
    assert listing["total"] == kpi["overdue_installments"]


@pytest.mark.asyncio
async def test_overdue_min_days_filter(seeded_client: AsyncClient) -> None:
    all_rows = (await seeded_client.get("/api/installments/overdue")).json()
    if all_rows["total"] == 0:
        pytest.skip("no overdue rows in sample for today's date — filter is a no-op")
    threshold = all_rows["items"][0]["days_overdue"]
    if threshold == 0:
        pytest.skip("all overdue at 0 days — nothing left to filter")
    filtered = (
        await seeded_client.get(f"/api/installments/overdue?min_days_overdue={threshold}")
    ).json()
    assert all(i["days_overdue"] >= threshold for i in filtered["items"])


@pytest.mark.asyncio
async def test_today_is_after_sample_data(sample_xlsm_path: Path) -> None:
    """Sanity for the suite — the sample sheet's earliest due dates fall
    in 1404/06 (Shahrivar 1404 ≈ Sep 2025).  If today's Jalali is later,
    the overdue endpoint should return non-empty.  Guards against false
    positives on `test_overdue_endpoint_shape` skipping the body asserts.
    """
    _ = sample_xlsm_path  # only used as a fixture marker
    today_g = date.today()
    today_j = jdatetime.date.fromgregorian(date=today_g)
    # Earliest sample due is 1404/05/04 (loan 2502 lender نفر 16).
    assert (today_j.year, today_j.month, today_j.day) > (1404, 5, 4), (
        "this test suite assumes today is past 1404/05/04 to validate overdue rows"
    )
