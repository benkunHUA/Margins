"""documents.parse_mode

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-08
"""

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "documents",
        sa.Column("parse_mode", sa.String(length=16), nullable=False, server_default="mineru"),
    )


def downgrade() -> None:
    op.drop_column("documents", "parse_mode")
