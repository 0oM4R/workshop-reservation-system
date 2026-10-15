"""Shared fixtures: a `workshops_test` engine with the real migrations applied."""

import os
import subprocess
import sys
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from app.models import Base
from app.settings import settings

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
    """Engine on `workshops_test`, its schema rebuilt once by the real migrations."""
    run_alembic("downgrade", "base")
    run_alembic("upgrade", "head")
    engine = create_async_engine(settings.test_database_url)
    yield engine
    await engine.dispose()


@pytest.fixture
async def engine(migrated_engine: AsyncEngine) -> AsyncEngine:
    """The test engine, with every table emptied before the test runs."""
    # Before, not after: a crashed test can't leak rows into the next one, and
    # the last test's rows stay behind for inspection.
    tables = ", ".join(Base.metadata.tables)
    async with migrated_engine.begin() as connection:
        await connection.execute(text(f"TRUNCATE {tables} RESTART IDENTITY"))
    return migrated_engine
