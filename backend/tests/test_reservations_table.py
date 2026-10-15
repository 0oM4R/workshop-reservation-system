"""Tests for the one-active-seat-per-email index on reservations."""

from datetime import UTC, datetime

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

INSERT_RESERVATION = text(
    "INSERT INTO reservations (workshop_id, name, email) "
    "VALUES (:workshop_id, 'Ann', :email)"
)


async def insert_workshop(connection: AsyncConnection) -> int:
    """Insert a workshop and return its id."""
    result = await connection.execute(
        text(
            "INSERT INTO workshops (slug, title, starts_at, capacity) "
            "VALUES ('w', 'W', :starts_at, 5) RETURNING id"
        ),
        {"starts_at": datetime.now(UTC)},
    )
    return result.scalar_one()


async def test_second_active_reservation_in_any_case_is_rejected(
    engine: AsyncEngine,
) -> None:
    """The same email in another letter case can't hold two active seats."""
    async with engine.begin() as connection:
        workshop_id = await insert_workshop(connection)
        await connection.execute(
            INSERT_RESERVATION, {"workshop_id": workshop_id, "email": "ann@example.com"}
        )

    with pytest.raises(IntegrityError, match="reservations_one_active_per_email"):
        async with engine.begin() as connection:
            await connection.execute(
                INSERT_RESERVATION,
                {"workshop_id": workshop_id, "email": "ANN@Example.com"},
            )


async def test_reservation_after_cancellation_is_allowed(engine: AsyncEngine) -> None:
    """A cancelled reservation frees the email for a new active one."""
    async with engine.begin() as connection:
        workshop_id = await insert_workshop(connection)
        params = {"workshop_id": workshop_id, "email": "ann@example.com"}
        await connection.execute(INSERT_RESERVATION, params)
        await connection.execute(text("UPDATE reservations SET status = 'cancelled'"))
        await connection.execute(INSERT_RESERVATION, params)

        count = await connection.scalar(text("SELECT count(*) FROM reservations"))

    assert count == 2
