"""Cross-site writes are refused; same-site and header-less (non-browser) pass."""

from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_cross_site_write_is_refused(client: AsyncClient) -> None:
    r = await client.post("/api/imports", headers={"Origin": "https://evil.example"})
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_same_site_write_passes_the_guard(client: AsyncClient) -> None:
    r = await client.post("/api/imports", headers={"Origin": "http://test"})
    assert r.status_code != 403  # reaches the endpoint (422: no files)


@pytest.mark.asyncio
async def test_reads_are_never_blocked(client: AsyncClient) -> None:
    r = await client.get("/api/health", headers={"Origin": "https://evil.example"})
    assert r.status_code == 200
