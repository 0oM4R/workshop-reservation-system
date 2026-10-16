"""Tests for GET /api/workshops."""

from datetime import UTC, datetime, timedelta

from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.helpers import CreateWorkshop


async def test_lists_workshops_by_start_time_with_remaining(
    client: AsyncClient, engine: AsyncEngine, create_workshop: CreateWorkshop
) -> None:
    """Shape is fixed, remaining = capacity - reserved, soonest first."""
    now = datetime.now(UTC)
    later = await create_workshop(
        "later", capacity=4, starts_at=now + timedelta(days=2)
    )
    sooner = await create_workshop(
        "sooner", capacity=10, starts_at=now + timedelta(days=1)
    )
    # Shortcut until reserve() exists (task 4.2): sets the counter without
    # reservation rows. Replace with three real reservations then.
    async with engine.begin() as connection:
        await connection.execute(
            text("UPDATE workshops SET reserved = 3 WHERE id = :id"), {"id": sooner}
        )

    response = await client.get("/api/workshops")

    assert response.status_code == 200
    body = response.json()
    assert [workshop["id"] for workshop in body] == [sooner, later]
    assert set(body[0]) == {"id", "title", "starts_at", "capacity", "remaining"}
    assert body[0]["remaining"] == 7
    assert body[1]["remaining"] == 4
