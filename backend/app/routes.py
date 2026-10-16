"""HTTP routes under `/api`: validate input, call a service, shape the response."""

from collections.abc import Sequence

from fastapi import APIRouter

from app.db import SessionDep
from app.schemas import WorkshopOut
from app.services import workshops

router = APIRouter(prefix="/workshops")


@router.get("", response_model=list[WorkshopOut])
async def list_workshops(session: SessionDep) -> Sequence[workshops.WorkshopRow]:
    """List workshops by start time with the seats left in each."""
    return await workshops.list_workshops(session)
