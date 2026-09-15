"""eval item detail columns

Revision ID: 0006
Revises: 0005
Create Date: 2026-09-15
"""

import sqlalchemy as sa
from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "eval_run_items",
        sa.Column("question", sa.Text(), nullable=False, server_default=""),
    )
    op.add_column(
        "eval_run_items",
        sa.Column("diagnostics_json", sa.Text(), nullable=False, server_default="{}"),
    )


def downgrade() -> None:
    op.drop_column("eval_run_items", "diagnostics_json")
    op.drop_column("eval_run_items", "question")
