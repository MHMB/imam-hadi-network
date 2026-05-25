"""FastAPI application entrypoint.

Run with::

    uvicorn app.main:app --reload
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app import __version__
from app.config import settings
from app.db import SessionLocal
from app.logging import configure_logging, get_logger
from app.routers import kpi as kpi_router

log = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Process lifecycle hooks."""
    configure_logging()
    log.info("api.startup", env=settings.app_env, version=__version__)
    yield
    log.info("api.shutdown")


app = FastAPI(
    title="Imam Hadi Network API",
    version=__version__,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

app.include_router(kpi_router.router)


@app.get("/api/health", tags=["meta"])
async def health() -> dict[str, str]:
    """Liveness + DB connectivity check."""
    db_ok = "ok"
    try:
        async with SessionLocal() as session:
            await session.execute(text("SELECT 1"))
    except Exception as exc:  # pragma: no cover — defensive
        log.error("health.db_failed", error=str(exc))
        db_ok = "fail"
    return {"db": db_ok, "version": __version__}


@app.get("/api/version", tags=["meta"])
async def version() -> dict[str, str]:
    """Return application version (also reported by /api/health)."""
    return {"version": __version__}
