"""Unit tests for the in-process broadcaster (no database involved)."""

from app.events import InProcessBroadcaster, SeatsChanged

EVENT = SeatsChanged(workshop_id=1, remaining=4)


async def test_every_subscriber_receives_the_event() -> None:
    """Fan-out: two subscribers each get their own copy."""
    broadcaster = InProcessBroadcaster()

    async with broadcaster.subscribe() as first, broadcaster.subscribe() as second:
        broadcaster.fan_out(EVENT)

        assert first.get_nowait() == EVENT
        assert second.get_nowait() == EVENT


async def test_leaving_the_block_unsubscribes() -> None:
    """A subscriber that exits stops being counted and stops receiving."""
    broadcaster = InProcessBroadcaster()

    async with broadcaster.subscribe():
        assert broadcaster.subscriber_count == 1

    assert broadcaster.subscriber_count == 0


async def test_slow_subscriber_is_dropped_and_others_keep_receiving() -> None:
    """A full queue ends that subscriber's stream without touching the rest."""
    broadcaster = InProcessBroadcaster(queue_size=2)

    async with broadcaster.subscribe() as slow, broadcaster.subscribe() as fast:
        for remaining in range(3):
            broadcaster.fan_out(SeatsChanged(1, remaining))
            fast.get_nowait()

        assert broadcaster.subscriber_count == 1
        # The dropped subscriber's backlog is discarded; only the end marker remains.
        assert slow.get_nowait() is None
        assert slow.empty()

        broadcaster.fan_out(EVENT)
        assert fast.get_nowait() == EVENT


async def test_close_all_ends_every_stream() -> None:
    """Closing wakes each subscriber with the end marker."""
    broadcaster = InProcessBroadcaster()

    async with broadcaster.subscribe() as first, broadcaster.subscribe() as second:
        broadcaster.close_all()

        assert first.get_nowait() is None
        assert second.get_nowait() is None
        assert broadcaster.subscriber_count == 0


def test_event_json_round_trips_with_only_the_two_fields() -> None:
    """The wire payload is exactly {workshop_id, remaining}."""
    assert EVENT.to_json() == '{"workshop_id": 1, "remaining": 4}'
    assert SeatsChanged.from_json(EVENT.to_json()) == EVENT
