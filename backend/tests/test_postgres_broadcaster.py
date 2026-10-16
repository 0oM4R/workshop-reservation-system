"""LISTEN/NOTIFY broadcaster: same behaviour as in-process, across processes."""

import asyncio
from collections.abc import AsyncIterator

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.events import NOTIFY_CHANNEL, PostgresBroadcaster, SeatsChanged
from app.settings import settings
from tests.helpers import CreateWorkshop, cancel, reserve

TIMEOUT_SECONDS = 5
PLAIN_DSN = settings.test_database_url.replace("postgresql+asyncpg://", "postgresql://")


async def started_broadcaster() -> PostgresBroadcaster:
    """Start a broadcaster and wait until its LISTEN is active."""
    broadcaster = PostgresBroadcaster(PLAIN_DSN)
    await broadcaster.start()
    async with asyncio.timeout(TIMEOUT_SECONDS):
        await broadcaster.listening.wait()
    return broadcaster


@pytest.fixture
async def process_a() -> AsyncIterator[PostgresBroadcaster]:
    """The listener of the API process that handles the requests (this one)."""
    broadcaster = await started_broadcaster()
    yield broadcaster
    await broadcaster.stop()


@pytest.fixture
async def process_b() -> AsyncIterator[PostgresBroadcaster]:
    """The broadcaster of a second API process, with its own LISTEN connection."""
    broadcaster = await started_broadcaster()
    yield broadcaster
    await broadcaster.stop()


async def test_event_reaches_a_client_of_another_process(
    client: AsyncClient,
    process_a: PostgresBroadcaster,
    process_b: PostgresBroadcaster,
    create_workshop: CreateWorkshop,
) -> None:
    """A reserve and a cancel handled by A are seen by a subscriber of B and of A."""
    workshop_id = await create_workshop(capacity=3)

    async with process_b.subscribe() as remote, process_a.subscribe() as local:
        await reserve(client, workshop_id)
        await cancel(client, workshop_id)

        async with asyncio.timeout(TIMEOUT_SECONDS):
            assert await remote.get() == SeatsChanged(workshop_id, 2)
            assert await remote.get() == SeatsChanged(workshop_id, 3)
            assert await local.get() == SeatsChanged(workshop_id, 2)
            assert await local.get() == SeatsChanged(workshop_id, 3)


async def test_rolled_back_and_repeated_requests_send_nothing(
    client: AsyncClient,
    process_b: PostgresBroadcaster,
    create_workshop: CreateWorkshop,
) -> None:
    """A 409, a repeat or a no-op cancel never notifies: only real changes arrive."""
    workshop_id = await create_workshop(capacity=1)

    async with process_b.subscribe() as remote:
        await reserve(client, workshop_id, email="a@example.com")
        full = await reserve(client, workshop_id, email="b@example.com")
        await reserve(client, workshop_id, email="a@example.com")
        await cancel(client, workshop_id, email="stranger@example.com")
        await cancel(client, workshop_id, email="a@example.com")
        await cancel(client, workshop_id, email="a@example.com")
        await reserve(client, workshop_id, email="c@example.com")

        assert full.status_code == 409
        # NOTIFYs arrive in commit order, so a stray one would come between these.
        async with asyncio.timeout(TIMEOUT_SECONDS):
            assert await remote.get() == SeatsChanged(workshop_id, 0)
            assert await remote.get() == SeatsChanged(workshop_id, 1)
            assert await remote.get() == SeatsChanged(workshop_id, 0)


async def test_notify_is_not_delivered_before_commit(
    engine: AsyncEngine, process_b: PostgresBroadcaster
) -> None:
    """Postgres holds a NOTIFY until its transaction commits."""
    event = SeatsChanged(workshop_id=1, remaining=9)

    async with process_b.subscribe() as remote, engine.connect() as connection:
        await connection.execute(
            text("SELECT pg_notify(:channel, :payload)"),
            {"channel": NOTIFY_CHANNEL, "payload": event.to_json()},
        )
        await asyncio.sleep(0.2)
        assert remote.empty()

        await connection.commit()

        async with asyncio.timeout(TIMEOUT_SECONDS):
            assert await remote.get() == event


async def test_listener_reconnects_after_its_connection_dies(
    engine: AsyncEngine, process_b: PostgresBroadcaster
) -> None:
    """Killing the LISTEN backend ends open streams on reconnect, then events flow."""
    async with process_b.subscribe() as before:
        async with engine.begin() as connection:
            await connection.execute(
                text(
                    "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                    "WHERE query LIKE 'LISTEN%' AND pid <> pg_backend_pid() "
                    "AND datname = current_database()"
                )
            )

        async with asyncio.timeout(TIMEOUT_SECONDS):
            assert await before.get() is None  # clients must reconnect and re-fetch
            await process_b.listening.wait()

    event = SeatsChanged(workshop_id=2, remaining=1)
    async with process_b.subscribe() as after:
        async with engine.begin() as connection:
            await connection.execute(
                text("SELECT pg_notify(:channel, :payload)"),
                {"channel": NOTIFY_CHANNEL, "payload": event.to_json()},
            )
        async with asyncio.timeout(TIMEOUT_SECONDS):
            assert await after.get() == event


async def test_client_subscribed_before_listen_is_told_to_refetch() -> None:
    """A client that joined before LISTEN was active may have missed events."""
    broadcaster = PostgresBroadcaster(PLAIN_DSN)
    try:
        async with broadcaster.subscribe() as early:
            await broadcaster.start()
            async with asyncio.timeout(TIMEOUT_SECONDS):
                assert await early.get() is None  # reconnect and re-fetch
    finally:
        await broadcaster.stop()
