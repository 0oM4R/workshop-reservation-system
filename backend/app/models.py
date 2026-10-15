"""SQLAlchemy models."""

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, func, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Declarative base for all models."""


class Workshop(Base):
    """A workshop with a fixed number of seats."""

    __tablename__ = "workshops"
    __table_args__ = (
        CheckConstraint(
            "reserved BETWEEN 0 AND capacity", name="reserved_within_capacity"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(unique=True)
    title: Mapped[str]
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    capacity: Mapped[int]
    reserved: Mapped[int] = mapped_column(default=0, server_default="0")


class Reservation(Base):
    """One person's seat in a workshop, active until cancelled."""

    __tablename__ = "reservations"
    __table_args__ = (
        CheckConstraint(
            "status IN ('active', 'cancelled')", name="status_active_or_cancelled"
        ),
        # The ON CONFLICT target when reserving: one active seat per email.
        Index(
            "reservations_one_active_per_email",
            "workshop_id",
            text("lower(email)"),
            unique=True,
            postgresql_where=text("status = 'active'"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    workshop_id: Mapped[int] = mapped_column(ForeignKey("workshops.id"))
    name: Mapped[str]
    email: Mapped[str]
    status: Mapped[str] = mapped_column(server_default="active")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    # onupdate fires only for SQLAlchemy update(); raw SQL must set updated_at.
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
