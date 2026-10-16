"""Tests for the SSE event stream of GET /api/events."""

import asyncio
from collections.abc import AsyncGenerator

import pytest
from sse_starlette import ServerSentEvent
from sse_starlette.sse import SendTimeoutError
from starlette.types import Message

from app import routes
from app.events import InProcessBroadcaster, SeatsChanged
from app.routes import seat_events

TIMEOUT_SECONDS = 5


async def next_event(stream: AsyncGenerator[ServerSentEvent]) -> ServerSentEvent:
    """Await the stream's next event."""
    return await anext(stream)


async def test_stream_emits_each_published_event_as_json() -> None:
    """A connected client receives the compact payload."""
    broadcaster = InProcessBroadcaster()
    stream = seat_events(broadcaster)
    first = asyncio.create_task(next_event(stream))
    await asyncio.sleep(0)  # let the stream subscribe

    broadcaster.fan_out(SeatsChanged(7, 2))

    async with asyncio.timeout(TIMEOUT_SECONDS):
        event = await first
    assert event.data == '{"workshop_id": 7, "remaining": 2}'
    await stream.aclose()


async def test_closing_the_stream_removes_the_subscriber() -> None:
    """A disconnecting client (generator cancelled) leaves no subscriber behind."""
    broadcaster = InProcessBroadcaster()
    stream = seat_events(broadcaster)
    waiting = asyncio.create_task(next_event(stream))
    await asyncio.sleep(0)
    assert broadcaster.subscriber_count == 1

    waiting.cancel()
    await asyncio.gather(waiting, return_exceptions=True)
    await stream.aclose()

    assert broadcaster.subscriber_count == 0


async def test_stream_ends_when_the_subscriber_is_dropped() -> None:
    """A dropped slow client's stream finishes so it can reconnect."""
    broadcaster = InProcessBroadcaster()
    stream = seat_events(broadcaster)
    waiting = asyncio.create_task(next_event(stream))
    await asyncio.sleep(0)

    broadcaster.close_all()

    async with asyncio.timeout(TIMEOUT_SECONDS):
        await asyncio.gather(waiting, return_exceptions=True)
    assert isinstance(waiting.exception(), StopAsyncIteration)


async def test_client_that_stops_reading_is_disconnected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A send that never completes ends the response and drops the subscriber."""
    monkeypatch.setattr(routes, "SEND_TIMEOUT_SECONDS", 0.1)
    broadcaster = InProcessBroadcaster()
    response = await routes.events(broadcaster)
    never = asyncio.Event()

    async def receive() -> Message:
        await never.wait()  # the client never disconnects
        return {"type": "http.disconnect"}

    async def send(message: Message) -> None:
        if message["type"] == "http.response.body":
            await never.wait()  # its socket buffer is full: the write never ends

    serving = asyncio.create_task(response({"type": "http"}, receive, send))
    async with asyncio.timeout(TIMEOUT_SECONDS):
        while broadcaster.subscriber_count == 0:
            await asyncio.sleep(0)
        broadcaster.fan_out(SeatsChanged(7, 2))
        with pytest.raises(SendTimeoutError):
            await serving

    assert broadcaster.subscriber_count == 0
