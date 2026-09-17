"""SQLite 单库索引：chunks.idx_id + chunk_fts + index_seq（替代 Faiss 与内存 BM25）

Revision ID: 0007
Revises: 0006
Create Date: 2026-09-17

说明：
- 按用户决定不迁移旧索引数据：直接重建 `chunks` 并删除 `faiss_seq`，
  实施后清空 `backend/data` 重新上传文档即可。
- `chunk_vectors`（vec0 虚表）由 `SqliteIndexBackend.initialize()` 按
  运行时配置的向量维度创建，迁移里只建与维度无关的 `chunk_fts` / `index_seq`。
"""

import sqlalchemy as sa
from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_table("chunks")
    op.drop_table("faiss_seq")

    op.create_table(
        "chunks",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "document_id",
            sa.String(36),
            sa.ForeignKey("documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("idx_id", sa.Integer(), nullable=False, unique=True),
        sa.Column("heading_path", sa.String(512), nullable=True),
        sa.Column("page", sa.Integer(), nullable=True),
        sa.Column("token_count", sa.Integer(), nullable=True),
        sa.Column("metadata_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("idx_chunks_document_id", "chunks", ["document_id"])
    op.create_index("idx_chunks_idx_id", "chunks", ["idx_id"], unique=True)

    op.create_table(
        "index_seq",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("next_id", sa.Integer(), nullable=False, server_default="0"),
    )
    op.execute("INSERT INTO index_seq (id, next_id) VALUES (1, 0)")

    # 稀疏索引：chunk_fts.rowid = chunks.idx_id，doc_title 等展示字段在 chunks.metadata_json
    op.execute(
        "CREATE VIRTUAL TABLE chunk_fts USING fts5("
        "tokens, chunk_id UNINDEXED, document_id UNINDEXED)"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS chunk_fts")
    op.drop_table("index_seq")
    op.drop_table("chunks")

    op.create_table(
        "chunks",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("document_id", sa.String(36), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("faiss_id", sa.Integer(), nullable=True),
        sa.Column("heading_path", sa.String(512), nullable=True),
        sa.Column("page", sa.Integer(), nullable=True),
        sa.Column("token_count", sa.Integer(), nullable=True),
        sa.Column("metadata_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_chunks_document_id", "chunks", ["document_id"])
    op.create_index("idx_chunks_faiss_id", "chunks", ["faiss_id"], unique=True)
    op.create_table(
        "faiss_seq",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("next_id", sa.Integer(), nullable=False, server_default="0"),
    )
    op.execute("INSERT INTO faiss_seq (id, next_id) VALUES (1, 0)")
