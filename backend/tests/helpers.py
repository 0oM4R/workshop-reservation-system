"""Types shared by fixtures and tests; conftest itself shouldn't be imported."""

from datetime import datetime
from typing import Protocol


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
