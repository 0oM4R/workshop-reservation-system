"""SQLAlchemy models."""

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime
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
