"""Smoke tests for /api/version and /api/health.

Health DB check may fail when no Postgres is reachable; that's expected in
unit-CI runs without the DB service, so we only assert the response shape.
"""

from __future__ import annotations

from httpx import AsyncClient


async def test_version(client: AsyncClient) -> None:
    r = await client.get("/api/version")
    assert r.status_code == 200
    body = r.json()
    assert "version" in body
    assert isinstance(body["version"], str)


async def test_health(client: AsyncClient) -> None:
    r = await client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert set(body.keys()) == {"db", "version"}
    assert body["db"] in {"ok", "fail"}
