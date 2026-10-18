"""Tests for the demo seed script."""

from datetime import UTC, datetime

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.seed import DEMO_WORKSHOPS, seed

SELECT_WORKSHOPS = text(
    "SELECT id, slug, title, description, starts_at, capacity, reserved "
    "FROM workshops ORDER BY id"
)


async def test_seeding_twice_leaves_the_same_rows(engine: AsyncEngine) -> None:
    """The second run inserts nothing and changes nothing."""
    async with engine.begin() as connection:
        first_written = await seed(connection)
        first_rows = (await connection.execute(SELECT_WORKSHOPS)).all()

    async with engine.begin() as connection:
        second_written = await seed(connection)
        second_rows = (await connection.execute(SELECT_WORKSHOPS)).all()

    assert first_written == len(DEMO_WORKSHOPS)
    assert second_written == 0
    assert second_rows == first_rows


async def test_seeding_fills_in_the_description_of_an_existing_workshop(
    engine: AsyncEngine,
) -> None:
    """A pre-description workshop gets one; nothing else changes."""
    pottery = DEMO_WORKSHOPS[0]
    # Not the seed's date or capacity, so a seed copying them fails.
    starts_at = datetime(2030, 1, 1, 10, tzinfo=UTC)
    async with engine.begin() as connection:
        await connection.execute(
            text(
                "INSERT INTO workshops (slug, title, starts_at, capacity, reserved) "
                "VALUES (:slug, :title, :starts_at, 9, 2)"
            ),
            {"slug": pottery.slug, "title": pottery.title, "starts_at": starts_at},
        )

    async with engine.begin() as connection:
        written = await seed(connection)
        row = (
            await connection.execute(
                text(
                    "SELECT description, starts_at, capacity, reserved "
                    "FROM workshops WHERE slug = :slug"
                ),
                {"slug": pottery.slug},
            )
        ).one()

    assert written == len(DEMO_WORKSHOPS)
    assert row.description == pottery.description
    assert (row.starts_at, row.capacity, row.reserved) == (starts_at, 9, 2)
