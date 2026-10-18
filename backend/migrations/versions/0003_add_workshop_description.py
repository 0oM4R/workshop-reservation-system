"""Add workshop descriptions for search.

Revision ID: 0003
Revises: 0002
"""

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add `description`, empty until the seed fills it."""
    op.add_column(
        "workshops",
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
    )


def downgrade() -> None:
    """Drop `description`."""
    op.drop_column("workshops", "description")
