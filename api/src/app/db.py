"""Async SQLAlchemy engine and session factory.

Exposes:

- ``engine``        — module-level async engine (created once).
- ``SessionLocal``  — async session factory.
- ``get_session``   — FastAPI dependency yielding an ``AsyncSession``.

Tests can swap the engine by overriding the ``get_session`` dependency.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import settings

# Single engine per process.  ``psycopg`` async driver, pool size kept modest;
# scale up only when API latency demands.
engine = create_async_engine(
    str(settings.database_url),
    echo=False,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=5,
)

SessionLocal = async_sessionmaker(
    bind=engine,
    expire_on_commit=False,
    autoflush=False,
)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency: yields an ``AsyncSession`` and closes it."""
    async with SessionLocal() as session:
        yield session


SessionDep = Annotated[AsyncSession, Depends(get_session)]
