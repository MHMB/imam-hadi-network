"""Shared pytest fixtures."""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"
SAMPLE_XLSM = FIXTURES_DIR / "sample_data-14050208.xlsm"


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    """Async HTTP client bound to the in-process FastAPI app."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def sample_xlsm_path() -> Path:
    """Absolute path to the anonymized sample workbook."""
    assert SAMPLE_XLSM.exists(), f"missing fixture: {SAMPLE_XLSM}"
    return SAMPLE_XLSM


@pytest.fixture
async def seeded_client(sample_xlsm_path: Path) -> AsyncIterator[AsyncClient]:
    """Client over a DB holding exactly the sample workbook (wiped before and after).

    Older test modules define their own copy; new ones use this one.
    """
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from app.config import settings
    from app.importer.runner import run_import
    from tests.db_tables import WIPE_TABLES

    engine = create_async_engine(str(settings.database_url))

    async def wipe() -> None:
        async with engine.begin() as conn:
            for t in WIPE_TABLES:
                await conn.exec_driver_sql(f"DELETE FROM {t}")

    await wipe()
    async with async_sessionmaker(engine, expire_on_commit=False)() as session:
        await run_import(session, sample_xlsm_path)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    await wipe()
    await engine.dispose()
