"""Request and response bodies of the API."""

from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, EmailStr, StringConstraints


class WorkshopOut(BaseModel):
    """A workshop with its remaining seats."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    starts_at: datetime
    capacity: int
    remaining: int


NAME_MAX_LENGTH = 100


class ReserveIn(BaseModel):
    """Who is reserving a seat."""

    name: Annotated[
        str,
        StringConstraints(
            strip_whitespace=True,
            min_length=1,
            max_length=NAME_MAX_LENGTH,
            # Postgres text can't store NUL; reject it as a 422 instead of a 500.
            pattern=r"^[^\x00]+$",
        ),
    ]
    email: EmailStr


class ReservationOut(BaseModel):
    """A held seat; never carries anyone's email."""

    id: int
    workshop_id: int
    name: str
    remaining: int


class CancelIn(BaseModel):
    """The email a seat was reserved with."""

    email: EmailStr


class CancelOut(BaseModel):
    """Same answer whether or not a seat was released."""

    message: str
