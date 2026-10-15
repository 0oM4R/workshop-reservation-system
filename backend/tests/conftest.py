"""Shared fixtures: a `workshops_test` engine with the real migrations applied."""

import os
import subprocess
import sys
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

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


@pytest.fixture
async def engine() -> AsyncIterator[AsyncEngine]:
    """Engine on `workshops_test` with the schema built by the real migrations."""
    # ponytail: rebuilds the schema per test (two subprocesses each); task 2.5
    # replaces this with one migration per session and truncation between tests.
    run_alembic("downgrade", "base")
    run_alembic("upgrade", "head")
    engine = create_async_engine(settings.test_database_url)
    yield engine
    await engine.dispose()
