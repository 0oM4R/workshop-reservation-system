"""The live stream works through nginx.

Needs the stack up (`docker compose up -d --wait`); run with `uv run pytest smoke`.
"""

import asyncio
import json
import uuid

import httpx

WEB_URL = "http://localhost:8080"
EVENT_TIMEOUT_SECONDS = 5
# Headers arrive before the server has registered the subscriber.
SUBSCRIBE_SETTLE_SECONDS = 0.5


async def wait_for_event(
    lines: httpx.Response, workshop_id: int, remaining: int
) -> dict[str, int]:
    """Read the stream until the event for this workshop and seat count arrives."""
    async for line in lines.aiter_lines():
        if not line.startswith("data:"):
            continue
        event = json.loads(line.removeprefix("data:"))
        if event["workshop_id"] == workshop_id and event["remaining"] == remaining:
            return event
    msg = "stream ended before the expected event"
    raise AssertionError(msg)


async def test_reserve_reaches_a_stream_client_through_nginx() -> None:
    """Open the stream, reserve a seat, and see the event within seconds."""
    email = f"smoke-{uuid.uuid4().hex}@example.com"
    async with httpx.AsyncClient(base_url=WEB_URL, timeout=None) as client:
        workshops = (await client.get("/api/workshops")).json()
        workshop = next(item for item in workshops if item["remaining"] > 0)
        reserved_path = f"/api/workshops/{workshop['id']}/reservations"

        async with client.stream("GET", "/api/events") as stream:
            assert stream.headers["content-type"].startswith("text/event-stream")
            await asyncio.sleep(SUBSCRIBE_SETTLE_SECONDS)
            try:
                reserved = await client.post(
                    reserved_path, json={"name": "Smoke Test", "email": email}
                )
                assert reserved.status_code == 201
                async with asyncio.timeout(EVENT_TIMEOUT_SECONDS):
                    event = await wait_for_event(
                        stream, workshop["id"], workshop["remaining"] - 1
                    )
            finally:
                # Leave the seat count as it was found.
                await client.post(f"{reserved_path}/cancel", json={"email": email})

    assert event == {
        "workshop_id": workshop["id"],
        "remaining": workshop["remaining"] - 1,
    }
