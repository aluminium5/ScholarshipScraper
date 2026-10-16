"""Engine and session wiring.

Serverless functions are frozen between invocations, so a pooled connection is
useless at best and a leaked Neon connection at worst: use NullPool and let the
Neon pooler do the pooling (spec §4).
"""

from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import NullPool

from backend.config import settings


class Base(DeclarativeBase):
    pass


def _engine_kwargs() -> dict:
    if settings.is_sqlite:
        # check_same_thread=False: FastAPI may touch a session from a worker thread.
        return {"connect_args": {"check_same_thread": False}}
    return {
        "poolclass": NullPool,
        "pool_pre_ping": True,
        "connect_args": {"connect_timeout": 10},
    }


engine = create_engine(settings.database_url, future=True, **_engine_kwargs())

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def init_db() -> None:
    """Create tables if they don't exist. Imported for the model metadata."""
    from backend import models  # noqa: F401

    Base.metadata.create_all(bind=engine)


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
