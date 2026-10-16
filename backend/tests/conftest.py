"""Test fixtures: an isolated SQLite database and an authenticated client."""

from __future__ import annotations

import os
import tempfile
from collections.abc import Iterator
from pathlib import Path

import pytest

# Point the app at a scratch database before any backend module is imported,
# so the engine is built against it rather than the developer's local file.
_TMP_DIR = Path(tempfile.mkdtemp(prefix="scholartrack-tests-"))
os.environ["DATABASE_URL"] = f"sqlite:///{(_TMP_DIR / 'test.db').as_posix()}"
os.environ["JWT_SECRET"] = "test-secret"
os.environ["CRON_SECRET"] = "test-cron-secret"
os.environ["ADMIN_EMAILS"] = "admin@example.com"

from fastapi.testclient import TestClient  # noqa: E402

from backend.db import Base, SessionLocal, engine  # noqa: E402
from backend.main import app  # noqa: E402


@pytest.fixture(autouse=True)
def _clean_database() -> Iterator[None]:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def _register(client: TestClient, email: str, password: str = "correct-horse-1") -> str:
    response = client.post(
        "/api/auth/signup",
        json={"name": email.split("@")[0].title(), "email": email, "password": password},
    )
    assert response.status_code == 201, response.text
    return response.json()["access_token"]


@pytest.fixture
def token(client: TestClient) -> str:
    return _register(client, "student@example.com")


@pytest.fixture
def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def other_auth(client: TestClient) -> dict[str, str]:
    """A second user, for checking that data is scoped per account."""
    return {"Authorization": f"Bearer {_register(client, 'other@example.com')}"}


@pytest.fixture
def admin_auth(client: TestClient) -> dict[str, str]:
    return {"Authorization": f"Bearer {_register(client, 'admin@example.com')}"}


@pytest.fixture
def make_scholarship(db):
    """Insert a scholarship row directly, bypassing the scrapers."""
    from datetime import date, timedelta

    from backend.models import Scholarship

    counter = {"n": 0}

    def _make(**overrides):
        counter["n"] += 1
        n = counter["n"]
        defaults = {
            "source": "manual",
            "external_id": f"seed-{n}",
            "title": f"Test Scholarship {n}",
            "provider": "Test Provider",
            "apply_url": f"https://example.org/scholarship/{n}",
            "info_url": f"https://example.org/scholarship/{n}/info",
            "deadline": date.today() + timedelta(days=n),
            "level": "ug",
            "tags": ["merit"],
            "is_active": True,
        }
        defaults.update(overrides)
        row = Scholarship(**defaults)
        db.add(row)
        db.commit()
        db.refresh(row)
        return row

    return _make
