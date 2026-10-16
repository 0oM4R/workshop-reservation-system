"""Tests for POST /api/workshops/{id}/reservations/cancel."""

import asyncio
import random
from collections.abc import Coroutine
from typing import Any

from httpx import AsyncClient, Response
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.helpers import CreateWorkshop, cancel, counters, reserve

PARALLEL_CANCELS = 10
MIXED_REQUESTS = 120
MIXED_WORKSHOP_CAPACITY = 3
MIXED_PEOPLE = 8
RESERVE_SHARE = 0.5


async def test_cancel_frees_the_seat(
    client: AsyncClient, engine: AsyncEngine, create_workshop: CreateWorkshop
) -> None:
    """A cancelled seat is released and the same email may reserve again."""
    workshop_id = await create_workshop(capacity=2)
    await reserve(client, workshop_id)

    response = await cancel(client, workshop_id, email="ADA@example.com")

    assert response.status_code == 200
    assert await counters(engine, workshop_id) == (0, 0)
    assert (await reserve(client, workshop_id)).status_code == 201


async def test_double_cancel_decrements_once(
    client: AsyncClient, engine: AsyncEngine, create_workshop: CreateWorkshop
) -> None:
    """The second cancel answers the same and releases nothing."""
    workshop_id = await create_workshop(capacity=2)
    await reserve(client, workshop_id, email="a@example.com")
    await reserve(client, workshop_id, email="b@example.com")

    first = await cancel(client, workshop_id, email="a@example.com")
    second = await cancel(client, workshop_id, email="a@example.com")

    assert second.status_code == 200
    assert second.json() == first.json()
    assert await counters(engine, workshop_id) == (1, 1)


async def test_cancel_for_unknown_email_looks_the_same(
    client: AsyncClient, engine: AsyncEngine, create_workshop: CreateWorkshop
) -> None:
    """An email that never reserved gets the same 200 and changes nothing."""
    workshop_id = await create_workshop(capacity=2)
    await reserve(client, workshop_id, email="a@example.com")
    await reserve(client, workshop_id, email="b@example.com")
    cancelled = await cancel(client, workshop_id, email="a@example.com")

    response = await cancel(client, workshop_id, email="stranger@example.com")

    assert response.status_code == 200
    assert response.json() == cancelled.json()
    assert await counters(engine, workshop_id) == (1, 1)


async def test_cancel_does_not_touch_other_people_or_workshops(
    client: AsyncClient, engine: AsyncEngine, create_workshop: CreateWorkshop
) -> None:
    """Only the matching email in the matching workshop loses its seat."""
    first = await create_workshop(capacity=2)
    second = await create_workshop(capacity=2)
    await reserve(client, first, email="a@example.com")
    await reserve(client, first, email="b@example.com")
    await reserve(client, second, email="a@example.com")

    await cancel(client, first, email="a@example.com")

    assert await counters(engine, first) == (1, 1)
    assert await counters(engine, second) == (1, 1)


async def test_cancel_in_unknown_workshop_returns_404(client: AsyncClient) -> None:
    """The one case that is not a 200."""
    response = await cancel(client, 999)

    assert response.status_code == 404


async def test_cancel_with_invalid_email_returns_422(
    client: AsyncClient, create_workshop: CreateWorkshop
) -> None:
    """The body is validated like every other input."""
    workshop_id = await create_workshop()

    response = await cancel(client, workshop_id, email="not-an-email")

    assert response.status_code == 422


async def test_parallel_cancels_decrement_once(
    client: AsyncClient, engine: AsyncEngine, create_workshop: CreateWorkshop
) -> None:
    """Racing cancels of one seat release it exactly once."""
    workshop_id = await create_workshop(capacity=3)
    await reserve(client, workshop_id, email="a@example.com")
    await reserve(client, workshop_id, email="b@example.com")

    responses = await asyncio.gather(
        *(cancel(client, workshop_id, "a@example.com") for _ in range(PARALLEL_CANCELS))
    )

    assert {response.status_code for response in responses} == {200}
    assert await counters(engine, workshop_id) == (1, 1)


async def test_reserved_equals_active_reservations_after_mixed_burst(
    client: AsyncClient, engine: AsyncEngine, create_workshop: CreateWorkshop
) -> None:
    """Racing reserves and cancels on tight workshops never skew the counter."""
    workshop_ids = [
        await create_workshop(capacity=MIXED_WORKSHOP_CAPACITY) for _ in range(2)
    ]
    rng = random.Random(0)  # fixed seed: a failure must be reproducible
    requests: list[Coroutine[Any, Any, Response]] = []
    for _ in range(MIXED_REQUESTS):
        workshop_id = rng.choice(workshop_ids)
        email = f"p{rng.randrange(MIXED_PEOPLE)}@example.com"
        action = reserve if rng.random() < RESERVE_SHARE else cancel
        requests.append(action(client, workshop_id, email=email))

    responses = await asyncio.gather(*requests)

    assert {response.status_code for response in responses} <= {200, 201, 409, 503}
    for workshop_id in workshop_ids:
        reserved, active = await counters(engine, workshop_id)
        assert reserved == active
        assert 0 <= reserved <= MIXED_WORKSHOP_CAPACITY
