"""query_logs

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-06
"""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "query_logs",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("session_id", sa.String(length=36), nullable=False),
        sa.Column("session_title", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="success"),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("total_ms", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("answer", sa.Text(), nullable=True),
        sa.Column("steps_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("citations_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("idx_query_logs_session_id", "query_logs", ["session_id"])
    op.create_index("idx_query_logs_status", "query_logs", ["status"])
    op.create_index("idx_query_logs_created_at", "query_logs", [sa.text("created_at DESC")])


def downgrade() -> None:
    op.drop_index("idx_query_logs_created_at", table_name="query_logs")
    op.drop_index("idx_query_logs_status", table_name="query_logs")
    op.drop_index("idx_query_logs_session_id", table_name="query_logs")
    op.drop_table("query_logs")
