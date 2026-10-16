"""Insert the demo workshops; safe to rerun.

Run with `python -m app.seed`.
"""

import asyncio
from datetime import UTC, datetime, timedelta

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncConnection, create_async_engine

from app.models import Workshop
from app.settings import settings

# (slug, title, days from today, capacity). Knife Skills has one seat, so
# the demo can show a full workshop after a single reservation.
DEMO_WORKSHOPS = [
    ("intro-to-pottery", "Intro to Pottery", 3, 8),
    ("watercolor-basics", "Watercolor Basics", 5, 12),
    ("sourdough-baking", "Sourdough Baking", 7, 10),
    ("bike-repair-101", "Bike Repair 101", 10, 6),
    ("knife-skills", "Knife Skills", 14, 1),
    ("photography-walk", "Photography Walk", 21, 15),
]


async def seed(connection: AsyncConnection) -> int:
    """Insert the demo workshops, skipping slugs that already exist.

    Returns:
        How many workshops were inserted.
    """
    # Relative to today, so a fresh database always shows upcoming workshops.
    ten_am_today = datetime.now(UTC).replace(hour=10, minute=0, second=0, microsecond=0)
    rows = [
        {
            "slug": slug,
            "title": title,
            "starts_at": ten_am_today + timedelta(days=days),
            "capacity": capacity,
        }
        for slug, title, days, capacity in DEMO_WORKSHOPS
    ]
    result = await connection.execute(
        insert(Workshop).values(rows).on_conflict_do_nothing(index_elements=["slug"])
    )
    return result.rowcount


async def main() -> None:
    """Seed the application database."""
    engine = create_async_engine(settings.database_url)
    async with engine.begin() as connection:
        inserted = await seed(connection)
    await engine.dispose()
    print(f"Inserted {inserted} demo workshops.")


if __name__ == "__main__":
    asyncio.run(main())
