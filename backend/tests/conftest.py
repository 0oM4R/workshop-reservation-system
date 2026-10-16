"""Shared fixtures: a `workshops_test` engine with the real migrations applied."""

import os
import subprocess
import sys
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from itertools import count
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import insert, make_url, text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.models import Base, Workshop
from app.settings import settings

# Must run before app.db is imported: it builds its engine from this URL, and
# no test may reach the dev database.
settings.database_url = settings.test_database_url

from app import db  # noqa: E402
from app.main import app  # noqa: E402
from tests.helpers import CreateWorkshop  # noqa: E402

BACKEND_DIR = Path(__file__).resolve().parents[1]


def run_alembic(*args: str) -> None:
    """Run Alembic against `workshops_test` in a subprocess."""
    subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=BACKEND_DIR,
        env={**os.environ, "DATABASE_URL": settings.test_database_url},
        check=True,
    )


@pytest.fixture(scope="session")
async def migrated_engine() -> AsyncIterator[AsyncEngine]:
    """The app's engine, its `workshops_test` schema rebuilt once by the migrations."""
    # Every test truncates tables through this engine, so refuse anything else.
    assert db.engine.url.database == make_url(settings.test_database_url).database, (
        "Tests must run against the test database"
    )
    run_alembic("downgrade", "base")
    run_alembic("upgrade", "head")
    yield db.engine
    await db.engine.dispose()


@pytest.fixture
async def engine(migrated_engine: AsyncEngine) -> AsyncEngine:
    """The test engine, with every table emptied before the test runs."""
    # Before, not after: a crashed test can't leak rows into the next one, and
    # the last test's rows stay behind for inspection.
    tables = ", ".join(Base.metadata.tables)
    async with migrated_engine.begin() as connection:
        await connection.execute(text(f"TRUNCATE {tables} RESTART IDENTITY"))
    return migrated_engine


@pytest.fixture
async def client(engine: AsyncEngine) -> AsyncIterator[AsyncClient]:
    """HTTP client for the app, on freshly emptied tables."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest.fixture
def create_workshop(engine: AsyncEngine) -> CreateWorkshop:
    """Insert a workshop and return its id."""
    numbers = count(1)

    async def create(
        slug: str | None = None, capacity: int = 5, starts_at: datetime | None = None
    ) -> int:
        slug = slug or f"workshop-{next(numbers)}"
        async with engine.begin() as connection:
            result = await connection.execute(
                insert(Workshop)
                .values(
                    slug=slug,
                    title=slug.title(),
                    starts_at=starts_at or datetime.now(UTC),
                    capacity=capacity,
                )
                .returning(Workshop.id)
            )
            return result.scalar_one()

    return create
