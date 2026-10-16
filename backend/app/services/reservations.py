"""Reserving seats: the only code that writes `workshops.reserved`."""

from dataclasses import dataclass

from sqlalchemy import ColumnElement, and_, func, literal_column, select, text, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Reservation, Workshop

# One retry covers an active reservation cancelled between our insert
# conflicting with it and our read of it.
MAX_ATTEMPTS = 2


class WorkshopNotFound(Exception):
    """No workshop has the requested id."""


class WorkshopFull(Exception):
    """Every seat of the workshop is taken."""


class ReservationBusy(Exception):
    """The active reservation was cancelled during every reserve attempt."""


@dataclass(frozen=True)
class ReserveResult:
    """The active reservation, the seats left, and whether this call created it."""

    reservation_id: int
    name: str
    remaining: int
    created: bool


async def reserve(
    session: AsyncSession, workshop_id: int, name: str, email: str
) -> ReserveResult:
    """Reserve one seat, or return the active reservation this email already holds.

    Raises:
        WorkshopNotFound: If no workshop has this id.
        WorkshopFull: If no seat is left.
        ReservationBusy: If both attempts race with cancellation.
    """
    for _ in range(MAX_ATTEMPTS):
        result = await _try_reserve(session, workshop_id, name, email)
        if result is not None:
            return result
    raise ReservationBusy(workshop_id)


async def _try_reserve(
    session: AsyncSession, workshop_id: int, name: str, email: str
) -> ReserveResult | None:
    """Run one reserve transaction; None means the conflicting row vanished."""
    async with session.begin():
        if not await _workshop_exists(session, workshop_id):
            raise WorkshopNotFound(workshop_id)

        inserted_id = await _insert_if_no_active(session, workshop_id, name, email)
        if inserted_id is None:
            return await _existing(session, workshop_id, email)

        remaining = await _take_seat(session, workshop_id)
        if remaining is None:
            raise WorkshopFull(workshop_id)
        return ReserveResult(inserted_id, name, remaining, created=True)


async def _workshop_exists(session: AsyncSession, workshop_id: int) -> bool:
    """Tell whether the workshop id is known."""
    found = await session.scalar(select(Workshop.id).where(Workshop.id == workshop_id))
    return found is not None


async def _insert_if_no_active(
    session: AsyncSession, workshop_id: int, name: str, email: str
) -> int | None:
    """Insert the reservation; None if this email already holds an active one."""
    # The conflict target is named: a bare DO NOTHING would hide other violations.
    statement = (
        insert(Reservation)
        .values(workshop_id=workshop_id, name=name, email=email)
        .on_conflict_do_nothing(
            index_elements=[Reservation.workshop_id, func.lower(Reservation.email)],
            # A literal, not a bound parameter: Postgres matches the partial index by
            # predicate text, so a $n placeholder finds no index to infer.
            index_where=text("status = 'active'"),
        )
        .returning(Reservation.id)
    )
    return await session.scalar(statement)


async def _take_seat(session: AsyncSession, workshop_id: int) -> int | None:
    """Count one more seat as reserved; return seats left, or None if full."""
    # The WHERE clause is the capacity gate: no seat check happens in Python.
    statement = (
        update(Workshop)
        .where(Workshop.id == workshop_id, Workshop.reserved < Workshop.capacity)
        .values(reserved=Workshop.reserved + 1)
        .returning(Workshop.capacity - Workshop.reserved)
    )
    return await session.scalar(statement)


async def _existing(
    session: AsyncSession, workshop_id: int, email: str
) -> ReserveResult | None:
    """Read the active reservation this email holds, with seats left."""
    statement = (
        select(
            Reservation.id,
            Reservation.name,
            (Workshop.capacity - Workshop.reserved).label("remaining"),
        )
        .join(Workshop, Workshop.id == Reservation.workshop_id)
        .where(_active_reservation(workshop_id, email))
    )
    row = (await session.execute(statement)).first()
    if row is None:
        return None
    return ReserveResult(row.id, row.name, row.remaining, created=False)


async def cancel(session: AsyncSession, workshop_id: int, email: str) -> bool:
    """Cancel the active reservation this email holds; return whether one existed.

    Cancelling twice, or an email that never reserved, changes nothing.

    Raises:
        WorkshopNotFound: If no workshop has this id.
    """
    async with session.begin():
        if not await _workshop_exists(session, workshop_id):
            raise WorkshopNotFound(workshop_id)

        if not await _mark_cancelled(session, workshop_id, email):
            return False
        await _release_seat(session, workshop_id)
        return True


async def _mark_cancelled(session: AsyncSession, workshop_id: int, email: str) -> bool:
    """Flip the active reservation to cancelled; False if there was none."""
    # Only the caller whose UPDATE changes the row may release the seat. A
    # concurrent cancel waits on the row lock, then sees status != 'active'.
    statement = (
        update(Reservation)
        .where(_active_reservation(workshop_id, email))
        .values(status="cancelled")
        .returning(Reservation.id)
    )
    return await session.scalar(statement) is not None


async def _release_seat(session: AsyncSession, workshop_id: int) -> None:
    """Count one fewer seat as reserved."""
    await session.execute(
        update(Workshop)
        .where(Workshop.id == workshop_id)
        .values(reserved=Workshop.reserved - 1)
    )


def _active_reservation(workshop_id: int, email: str) -> ColumnElement[bool]:
    """Match the active seat using the partial index's literal predicate."""
    return and_(
        Reservation.workshop_id == workshop_id,
        func.lower(Reservation.email) == func.lower(email),
        Reservation.status == literal_column("'active'"),
    )
