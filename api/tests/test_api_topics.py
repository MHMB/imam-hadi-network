"""Integration tests for ``GET /api/topics`` against the seeded sample."""

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


@pytest.mark.asyncio
async def test_topics_includes_seeded_catalog(seeded_client: AsyncClient) -> None:
    r = await seeded_client.get("/api/topics")
    assert r.status_code == 200, r.text
    body = r.json()
    names = {t["name"] for t in body}
    # Must contain every seeded topic name.
    for must in ("درمان", "ازدواج", "خانه", "نامعلوم", "وسیله نقلیه"):
        assert must in names


@pytest.mark.asyncio
async def test_topics_loan_counts_match_sample_1404(seeded_client: AsyncClient) -> None:
    r = await seeded_client.get("/api/topics?year=1404")
    body = r.json()
    by_name = {t["name"]: t for t in body}
    # 1404 sample loans by topic (from SPEC.md §2.4):
    # 1500 درمان, 1501 عتبات, 1502 وسیله نقلیه, 1503 خانه, 1504 خانه.
    assert by_name["درمان"]["loan_count"] == 1
    assert by_name["عتبات"]["loan_count"] == 1
    assert by_name["وسیله نقلیه"]["loan_count"] == 1
    assert by_name["خانه"]["loan_count"] == 2
    # Topics with no 1404 loans show up as zero — not omitted.
    assert by_name["ازدواج"]["loan_count"] == 0


@pytest.mark.asyncio
async def test_topics_year_filter_changes_counts(seeded_client: AsyncClient) -> None:
    """Without year filter the totals span both 1404 and 1405."""
    all_r = (await seeded_client.get("/api/topics")).json()
    y1404_r = (await seeded_client.get("/api/topics?year=1404")).json()
    by_name_all = {t["name"]: t["loan_count"] for t in all_r}
    by_name_1404 = {t["name"]: t["loan_count"] for t in y1404_r}
    # خانه appears in both years (1404 x2, 1405 x1 — see SPEC.md §2.5 loan 2503)
    assert by_name_all["خانه"] >= by_name_1404["خانه"]
    # Total loan count across topics equals 9 (sample total).
    assert sum(by_name_all.values()) == 9
    assert sum(by_name_1404.values()) == 5
