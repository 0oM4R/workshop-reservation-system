"""Request and response bodies of the API."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class WorkshopOut(BaseModel):
    """A workshop with its remaining seats."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    starts_at: datetime
    capacity: int
    remaining: int
