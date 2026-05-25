"""Application settings loaded from environment variables.

Settings are immutable per-process; importing `settings` is the only way
to access configuration.  Tests override via env vars or by constructing
a fresh ``Settings(...)`` instance.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, PostgresDsn
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All runtime configuration.

    Reads from environment variables (and ``.env`` in dev) — never from
    Python literals.  Add new options here, not scattered through modules.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- environment ---
    app_env: Literal["dev", "test", "prod"] = "dev"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    version: str = "0.1.0"

    # --- database ---
    database_url: PostgresDsn = Field(
        default=PostgresDsn(
            "postgresql+psycopg://imamhadi:imamhadi_dev_password@localhost:5433/imamhadi"
        ),
        description="SQLAlchemy URL with psycopg driver.  Async + sync share the same DSN.",
    )

    # --- importer ---
    upload_dir: Path = Path("./uploads")
    max_upload_mb: int = 50

    # --- API ---
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Cached settings accessor; safe to call from anywhere."""
    return Settings()


settings = get_settings()
