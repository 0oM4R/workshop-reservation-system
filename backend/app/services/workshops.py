"""Reading workshops."""

from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import Row, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Workshop

# Columns: id, title, description, starts_at, capacity, remaining.
WorkshopRow = Row[int, str, str, datetime, int, int]


async def list_workshops(session: AsyncSession) -> Sequence[WorkshopRow]:
    """Return all workshops with their remaining seats, soonest first."""
    statement = select(
        Workshop.id,
        Workshop.title,
        Workshop.description,
        Workshop.starts_at,
        Workshop.capacity,
        (Workshop.capacity - Workshop.reserved).label("remaining"),
    ).order_by(Workshop.starts_at, Workshop.id)
    result = await session.execute(statement)
    return result.all()
