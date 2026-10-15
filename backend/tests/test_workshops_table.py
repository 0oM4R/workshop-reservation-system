"""Tests for the workshops table constraints."""

from datetime import UTC, datetime

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine


async def test_reserved_above_capacity_is_rejected(engine: AsyncEngine) -> None:
    """The CHECK constraint refuses reserved > capacity."""
    insert = text(
        "INSERT INTO workshops (slug, title, starts_at, capacity, reserved) "
        "VALUES ('w', 'W', :starts_at, 2, 3)"
    )
    with pytest.raises(IntegrityError, match="reserved_within_capacity"):
        async with engine.begin() as connection:
            await connection.execute(insert, {"starts_at": datetime.now(UTC)})
