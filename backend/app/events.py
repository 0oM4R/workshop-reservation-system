"""Live seat-count events and the broadcasters that deliver them."""

import asyncio
import json
import logging
from collections.abc import AsyncGenerator
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from dataclasses import asdict, dataclass
from typing import Protocol

import asyncpg

from app.settings import settings

logger = logging.getLogger(__name__)

# A client further behind than this is dropped and re-fetches on reconnect.
SUBSCRIBER_QUEUE_SIZE = 64
NOTIFY_CHANNEL = "seats_changed"
RECONNECT_DELAY_SECONDS = 1.0


@dataclass(frozen=True)
class SeatsChanged:
    """A workshop's remaining seats changed; this is the whole payload."""

    workshop_id: int
    remaining: int

    def to_json(self) -> str:
        """Encode for an SSE data field or a NOTIFY payload."""
        return json.dumps(asdict(self))

    @classmethod
    def from_json(cls, payload: str) -> "SeatsChanged":
        """Decode a JSON object holding exactly these two fields."""
        return cls(**json.loads(payload))


# None is the end-of-stream marker sent to a dropped subscriber.
Subscription = asyncio.Queue[SeatsChanged | None]


class Broadcaster(Protocol):
    """Delivers `SeatsChanged` events to every open SSE client."""

    def subscribe(self) -> AbstractAsyncContextManager[Subscription]:
        """Register a client for the length of the `async with`."""
        ...

    async def start(self) -> None:
        """Acquire background resources when the app starts."""
        ...

    async def stop(self) -> None:
        """Release background resources when the app shuts down."""
        ...


class InProcessBroadcaster:
    """Fans events out to subscribers of this process through bounded queues."""

    def __init__(self, queue_size: int = SUBSCRIBER_QUEUE_SIZE) -> None:
        """Create a broadcaster whose subscribers each buffer `queue_size` events."""
        self._queue_size = queue_size
        self._subscribers: set[Subscription] = set()

    @property
    def subscriber_count(self) -> int:
        """Number of connected subscribers."""
        return len(self._subscribers)

    @asynccontextmanager
    async def subscribe(self) -> AsyncGenerator[Subscription]:
        """Register a subscriber; it is removed when the block exits."""
        queue: Subscription = asyncio.Queue(maxsize=self._queue_size)
        self._subscribers.add(queue)
        try:
            yield queue
        finally:
            self._subscribers.discard(queue)

    def fan_out(self, event: SeatsChanged) -> None:
        """Queue the event for every subscriber, dropping any that is full."""
        for queue in list(self._subscribers):
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                self._drop(queue)

    def close_all(self) -> None:
        """End every subscription so clients reconnect and re-fetch."""
        for queue in list(self._subscribers):
            self._drop(queue)

    def _drop(self, queue: Subscription) -> None:
        """Remove a subscriber and wake it with the end-of-stream marker."""
        self._subscribers.discard(queue)
        while not queue.empty():
            queue.get_nowait()
        queue.put_nowait(None)

    async def start(self) -> None:
        """Do nothing: no background resources."""

    async def stop(self) -> None:
        """Do nothing: no background resources."""


class PostgresBroadcaster:
    """Shares events across processes: seat updates NOTIFY, every process LISTENs."""

    def __init__(self, dsn: str) -> None:
        """Listen on a dedicated connection to `dsn`, a plain `postgresql://` URL."""
        self._dsn = dsn
        self._local = InProcessBroadcaster()
        self._listener: asyncio.Task[None] | None = None
        self.listening = asyncio.Event()

    def subscribe(self) -> AbstractAsyncContextManager[Subscription]:
        """Register a client of this process."""
        return self._local.subscribe()

    async def start(self) -> None:
        """Start the listener task."""
        self._listener = asyncio.create_task(self._listen_forever())

    async def stop(self) -> None:
        """Stop the listener task and end all subscriptions."""
        if self._listener is not None:
            self._listener.cancel()
            await asyncio.gather(self._listener, return_exceptions=True)
        self._local.close_all()

    async def _listen_forever(self) -> None:
        """Keep one LISTEN connection alive, reconnecting after any failure."""
        while True:
            try:
                await self._listen_until_disconnected()
            except (OSError, asyncpg.PostgresError, asyncpg.InterfaceError) as error:
                logger.warning("LISTEN connection failed: %s", error)
            except Exception:
                logger.exception("LISTEN connection failed unexpectedly")
            self.listening.clear()
            await asyncio.sleep(RECONNECT_DELAY_SECONDS)

    async def _listen_until_disconnected(self) -> None:
        """Listen on a fresh connection until it drops."""
        lost = asyncio.Event()
        connection = await asyncpg.connect(self._dsn)
        try:
            connection.add_termination_listener(lambda _connection: lost.set())
            await connection.add_listener(NOTIFY_CHANNEL, self._on_notify)
            # Events sent before this point were missed, so make clients re-fetch.
            self._local.close_all()
            self.listening.set()
            await lost.wait()
        finally:
            await connection.close()

    def _on_notify(
        self,
        _connection: object,
        _pid: int,
        _channel: str,
        payload: object,
        /,
    ) -> None:
        """Hand a received NOTIFY to the local subscribers."""
        try:
            event = SeatsChanged.from_json(str(payload))
        except (ValueError, TypeError) as error:
            logger.warning("Ignoring malformed %s payload: %s", NOTIFY_CHANNEL, error)
            return
        self._local.fan_out(event)


def build_broadcaster() -> Broadcaster:
    """Create the LISTEN/NOTIFY broadcaster for the application database."""
    dsn = settings.database_url.replace("postgresql+asyncpg://", "postgresql://", 1)
    return PostgresBroadcaster(dsn)


_broadcaster = build_broadcaster()


def get_broadcaster() -> Broadcaster:
    """FastAPI dependency: the process-wide broadcaster."""
    return _broadcaster
