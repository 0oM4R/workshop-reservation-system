"""Types shared by fixtures and tests; conftest itself shouldn't be imported."""

from datetime import datetime
from typing import Protocol

from httpx import AsyncClient, Response
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine


class CreateWorkshop(Protocol):
    """Insert a workshop and return its id."""

    async def __call__(
        self,
        slug: str | None = ...,
        capacity: int = ...,
        starts_at: datetime | None = ...,
    ) -> int:
        """Call signature of the `create_workshop` fixture."""
        ...


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


async def cancel(
    client: AsyncClient, workshop_id: int, email: str = "ada@example.com"
) -> Response:
    """POST a cancellation."""
    return await client.post(
        f"/api/workshops/{workshop_id}/reservations/cancel", json={"email": email}
    )
