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
