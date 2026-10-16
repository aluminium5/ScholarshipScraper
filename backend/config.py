"""Environment-driven settings.

Everything has a safe local default so `uvicorn backend.main:app` works with no
.env at all; production values come from Vercel's environment variables.
"""

from __future__ import annotations

import os
from functools import lru_cache


def _normalize_database_url(raw: str) -> str:
    """Make a Neon/Heroku-style URL usable by SQLAlchemy + psycopg 3.

    Neon hands out `postgres://...`; SQLAlchemy needs an explicit driver.
    """
    url = raw.strip()
    if url.startswith("postgres://"):
        return "postgresql+psycopg://" + url[len("postgres://") :]
    if url.startswith("postgresql://"):
        return "postgresql+psycopg://" + url[len("postgresql://") :]
    return url


class Settings:
    def __init__(self) -> None:
        raw_db = os.getenv("DATABASE_URL", "").strip()
        # SQLite fallback keeps local dev dependency-free (spec §2).
        self.database_url: str = (
            _normalize_database_url(raw_db) if raw_db else "sqlite:///./scholartrack.db"
        )
        self.is_sqlite: bool = self.database_url.startswith("sqlite")

        self.jwt_secret: str = os.getenv("JWT_SECRET", "dev-only-insecure-secret")
        self.jwt_algorithm: str = "HS256"
        self.jwt_expire_minutes: int = int(os.getenv("JWT_EXPIRE_MINUTES", str(60 * 24 * 14)))

        self.cron_secret: str = os.getenv("CRON_SECRET", "")

        self.admin_emails: set[str] = {
            e.strip().lower() for e in os.getenv("ADMIN_EMAILS", "").split(",") if e.strip()
        }

        # Production serves the frontend from the same origin, so CORS is only
        # needed for the Vite dev server.
        self.cors_origins: list[str] = [
            o.strip()
            for o in os.getenv(
                "CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
            ).split(",")
            if o.strip()
        ]

    @property
    def is_production(self) -> bool:
        return bool(os.getenv("VERCEL"))


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
