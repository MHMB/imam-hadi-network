"""Shared pytest fixtures.

P0: minimal — just an httpx client against the FastAPI app.
P1 will add a transactional ``db_session`` fixture.
P2 will add an ``xlsm_fixture_path`` pointing at the sample workbook.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    """Async HTTP client bound to the in-process FastAPI app."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
