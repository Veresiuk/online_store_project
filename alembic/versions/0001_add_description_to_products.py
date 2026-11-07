"""add description to products

Revision ID: 0001
Revises:
Create Date: 2026-03-29
"""

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "products", sa.Column("description", sa.String(length=255), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("products", "description")