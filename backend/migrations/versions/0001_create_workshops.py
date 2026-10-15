"""Create the workshops table.

Revision ID: 0001
Revises:
"""

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create `workshops` with the seat-count CHECK backstop."""
    op.create_table(
        "workshops",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("slug", sa.String(), nullable=False, unique=True),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("capacity", sa.Integer(), nullable=False),
        sa.Column("reserved", sa.Integer(), nullable=False, server_default="0"),
        sa.CheckConstraint(
            "reserved BETWEEN 0 AND capacity", name="reserved_within_capacity"
        ),
    )


def downgrade() -> None:
    """Drop `workshops`."""
    op.drop_table("workshops")
