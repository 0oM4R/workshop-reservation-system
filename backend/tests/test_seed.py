"""Tests for the demo seed script."""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.seed import DEMO_WORKSHOPS, seed

SELECT_WORKSHOPS = text(
    "SELECT id, slug, title, starts_at, capacity, reserved FROM workshops ORDER BY id"
)


async def test_seeding_twice_leaves_the_same_rows(engine: AsyncEngine) -> None:
    """The second run inserts nothing and changes nothing."""
    async with engine.begin() as connection:
        first_inserted = await seed(connection)
        first_rows = (await connection.execute(SELECT_WORKSHOPS)).all()

    async with engine.begin() as connection:
        second_inserted = await seed(connection)
        second_rows = (await connection.execute(SELECT_WORKSHOPS)).all()

    assert first_inserted == len(DEMO_WORKSHOPS)
    assert second_inserted == 0
    assert second_rows == first_rows
