"""HTTP routes under `/api`: validate input, call a service, shape the response."""

from collections.abc import Sequence
from typing import Annotated

from fastapi import APIRouter, Path, Response, status

from app.db import SessionDep
from app.schemas import (
    CancelIn,
    CancelOut,
    ReservationOut,
    ReserveIn,
    WorkshopOut,
)
from app.services import reservations, workshops

router = APIRouter(prefix="/workshops")
POSTGRES_INTEGER_MAX = 2_147_483_647
# Identical for every outcome, so a retried cancel never looks like a failure.
CANCEL_MESSAGE = "If this email held a seat, it has been cancelled."


@router.get("", response_model=list[WorkshopOut])
async def list_workshops(session: SessionDep) -> Sequence[workshops.WorkshopRow]:
    """List workshops by start time with the seats left in each."""
    return await workshops.list_workshops(session)


@router.post(
    "/{workshop_id}/reservations",
    response_model=ReservationOut,
    status_code=status.HTTP_201_CREATED,
)
async def reserve_seat(
    workshop_id: Annotated[int, Path(gt=0, le=POSTGRES_INTEGER_MAX)],
    body: ReserveIn,
    session: SessionDep,
    response: Response,
) -> ReservationOut:
    """Reserve a seat: 201 when new, 200 when this email already holds one."""
    result = await reservations.reserve(session, workshop_id, body.name, body.email)
    if not result.created:
        response.status_code = status.HTTP_200_OK
    return ReservationOut(
        id=result.reservation_id,
        workshop_id=workshop_id,
        name=result.name,
        remaining=result.remaining,
    )


@router.post("/{workshop_id}/reservations/cancel", response_model=CancelOut)
async def cancel_reservation(
    workshop_id: Annotated[int, Path(gt=0, le=POSTGRES_INTEGER_MAX)],
    body: CancelIn,
    session: SessionDep,
) -> CancelOut:
    """Cancel a seat: same 200 message, or 404 for an unknown workshop."""
    await reservations.cancel(session, workshop_id, body.email)
    return CancelOut(message=CANCEL_MESSAGE)
