"""Tests for POST /api/workshops/{id}/reservations."""

import asyncio

import pytest
from httpx import AsyncClient, Response
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.schemas import NAME_MAX_LENGTH
from tests.helpers import CreateWorkshop

RESERVATIONS_PER_BURST = 50


async def reserve(
    client: AsyncClient,
    workshop_id: int,
    email: str = "ada@example.com",
    name: str = "Ada",
) -> Response:
    """POST a reservation."""
    return await client.post(
        f"/api/workshops/{workshop_id}/reservations",
        json={"name": name, "email": email},
    )


async def counters(engine: AsyncEngine, workshop_id: int) -> tuple[int, int]:
    """Return (reserved, active reservation rows) for a workshop."""
    async with engine.connect() as connection:
        row = (
            await connection.execute(
                text(
                    "SELECT reserved, (SELECT count(*) FROM reservations "
                    "WHERE workshop_id = w.id AND status = 'active') "
                    "FROM workshops w WHERE id = :id"
                ),
                {"id": workshop_id},
            )
        ).one()
    return row[0], row[1]


@pytest.mark.parametrize(
    "body",
    [
        {"name": "", "email": "ada@example.com"},
        {"name": "   ", "email": "ada@example.com"},
        {"name": "Ada\x00", "email": "ada@example.com"},
        {"name": "Ad\x00a", "email": "ada@example.com"},
        {"name": "x" * (NAME_MAX_LENGTH + 1), "email": "ada@example.com"},
        {"name": "Ada", "email": "not-an-email"},
        {"name": "Ada"},
        {"email": "ada@example.com"},
    ],
)
async def test_invalid_input_returns_422(
    client: AsyncClient,
    engine: AsyncEngine,
    create_workshop: CreateWorkshop,
    body: dict[str, str],
) -> None:
    """Bad name or email never reaches the service."""
    workshop_id = await create_workshop()

    response = await client.post(
        f"/api/workshops/{workshop_id}/reservations", json=body
    )

    assert response.status_code == 422
    assert await counters(engine, workshop_id) == (0, 0)


@pytest.mark.parametrize("workshop_id", [-1, 0, 2_147_483_648, 10**30])
async def test_invalid_workshop_id_returns_422(
    client: AsyncClient, workshop_id: int
) -> None:
    """Reject ids outside the positive PostgreSQL integer range."""
    response = await reserve(client, workshop_id)

    assert response.status_code == 422


async def test_new_reservation_returns_201_without_email(
    client: AsyncClient, engine: AsyncEngine, create_workshop: CreateWorkshop
) -> None:
    """A new seat is 201, shows remaining, and leaks no email."""
    workshop_id = await create_workshop(capacity=3)

    response = await reserve(client, workshop_id, email="  Ada@Example.com  ")

    assert response.status_code == 201
    body = response.json()
    assert body["remaining"] == 2
    assert body["name"] == "Ada"
    assert "email" not in body
    assert await counters(engine, workshop_id) == (1, 1)


async def test_same_email_in_another_case_returns_existing_with_200(
    client: AsyncClient, engine: AsyncEngine, create_workshop: CreateWorkshop
) -> None:
    """A repeated email, in any letter case, gives the same reservation."""
    workshop_id = await create_workshop(capacity=3)
    first = await reserve(client, workshop_id, email="ada@example.com")

    second = await reserve(client, workshop_id, email="ADA@Example.COM")

    assert second.status_code == 200
    assert second.json() == first.json() | {"remaining": 2}
    assert await counters(engine, workshop_id) == (1, 1)


async def test_repeated_non_ascii_email_returns_existing_with_200(
    client: AsyncClient, engine: AsyncEngine, create_workshop: CreateWorkshop
) -> None:
    """Python and Postgres lowercase İ differently; the lookup must still match."""
    workshop_id = await create_workshop()
    await reserve(client, workshop_id, email="İda@example.com")

    second = await reserve(client, workshop_id, email="İda@example.com")

    assert second.status_code == 200
    assert await counters(engine, workshop_id) == (1, 1)


async def test_full_workshop_returns_409_and_counter_unchanged(
    client: AsyncClient, engine: AsyncEngine, create_workshop: CreateWorkshop
) -> None:
    """The last seat goes once; the next person gets 409 and no row."""
    workshop_id = await create_workshop(capacity=1)
    await reserve(client, workshop_id, email="a@example.com")

    response = await reserve(client, workshop_id, email="b@example.com")

    assert response.status_code == 409
    assert await counters(engine, workshop_id) == (1, 1)


@pytest.mark.parametrize("workshop_id", [999, 2_147_483_647])
async def test_unknown_workshop_returns_404(
    client: AsyncClient, workshop_id: int
) -> None:
    """No such workshop is 404."""
    response = await reserve(client, workshop_id)

    assert response.status_code == 404


async def test_parallel_reserves_never_exceed_capacity(
    client: AsyncClient, engine: AsyncEngine, create_workshop: CreateWorkshop
) -> None:
    """50 people race for 10 seats: exactly 10 win and the counter agrees."""
    capacity = 10
    workshop_id = await create_workshop(capacity=capacity)

    responses = await asyncio.gather(
        *(
            reserve(client, workshop_id, email=f"p{n}@example.com")
            for n in range(RESERVATIONS_PER_BURST)
        )
    )

    statuses = [response.status_code for response in responses]
    assert statuses.count(201) == capacity
    assert statuses.count(409) == RESERVATIONS_PER_BURST - capacity
    assert await counters(engine, workshop_id) == (capacity, capacity)


async def test_duplicate_burst_creates_one_reservation(
    client: AsyncClient, engine: AsyncEngine, create_workshop: CreateWorkshop
) -> None:
    """The same email sent 10 times at once: one 201, nine 200s, one row."""
    workshop_id = await create_workshop(capacity=5)

    responses = await asyncio.gather(*(reserve(client, workshop_id) for _ in range(10)))

    statuses = sorted(response.status_code for response in responses)
    assert statuses == [200] * 9 + [201]
    assert await counters(engine, workshop_id) == (1, 1)
