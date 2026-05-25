"""Integration tests for /api/imports + /api/issues."""

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
async def test_imports_list_shape_after_one_import(seeded_client: AsyncClient) -> None:
    r = await seeded_client.get("/api/imports")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["total"] == 1
    item = body["items"][0]
    assert item["status"] == "success"
    assert sorted(item["years_imported"]) == [1404, 1405]
    # Sample has 26 issues; 1 is severity=error (loan 2501 total_mismatch).
    assert item["issue_count"] == 26
    assert item["error_count"] == 1


@pytest.mark.asyncio
async def test_import_detail_includes_report(seeded_client: AsyncClient) -> None:
    listing = (await seeded_client.get("/api/imports")).json()
    import_id = listing["items"][0]["id"]
    r = await seeded_client.get(f"/api/imports/{import_id}")
    body = r.json()
    assert r.status_code == 200, r.text
    assert body["report"]["loans"] == 9
    assert body["report"]["persons"] == 21


@pytest.mark.asyncio
async def test_import_detail_404(seeded_client: AsyncClient) -> None:
    r = await seeded_client.get("/api/imports/999999")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_issues_list_defaults_to_latest_import(seeded_client: AsyncClient) -> None:
    r = await seeded_client.get("/api/issues")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["total"] == 26


@pytest.mark.asyncio
async def test_issues_filter_by_severity(seeded_client: AsyncClient) -> None:
    r = await seeded_client.get("/api/issues?severity=error")
    body = r.json()
    assert body["total"] == 1
    assert body["items"][0]["severity"] == "error"
    assert body["items"][0]["category"] == "total_mismatch"


@pytest.mark.asyncio
async def test_issues_filter_by_category(seeded_client: AsyncClient) -> None:
    r = await seeded_client.get("/api/issues?category=unknown_phone_format")
    body = r.json()
    # 21 persons + all blank phones → 21 unknown_phone_format warnings
    assert body["total"] == 21
