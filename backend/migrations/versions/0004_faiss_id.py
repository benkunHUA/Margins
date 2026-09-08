"""chunks.faiss_id + faiss_seq

Revision ID: 0004
Revises: 0003
Create Date: 2026-09-08
"""

import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("chunks", sa.Column("faiss_id", sa.Integer(), nullable=True))
    op.create_index("idx_chunks_faiss_id", "chunks", ["faiss_id"], unique=True)
    op.create_table(
        "faiss_seq",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("next_id", sa.Integer(), nullable=False, server_default="0"),
    )
    op.execute("INSERT INTO faiss_seq (id, next_id) VALUES (1, 0)")


def downgrade() -> None:
    op.execute("DELETE FROM faiss_seq")
    op.drop_table("faiss_seq")
    op.drop_index("idx_chunks_faiss_id", table_name="chunks")
    op.drop_column("chunks", "faiss_id")
