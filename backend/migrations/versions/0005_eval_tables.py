"""eval tables

Revision ID: 0005
Revises: 0004
Create Date: 2026-09-15
"""

import sqlalchemy as sa
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "eval_datasets",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("name", sa.String(length=100), nullable=False, unique=True),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("item_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("category_counts_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "eval_runs",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "dataset_id",
            sa.String(length=36),
            sa.ForeignKey("eval_datasets.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("mode", sa.String(length=16), nullable=False, server_default="retrieval"),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="queued"),
        sa.Column("configs_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("progress_done", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("progress_total", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("metrics_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
    )
    op.create_index("idx_eval_runs_dataset_id", "eval_runs", ["dataset_id"])
    op.create_index("idx_eval_runs_status", "eval_runs", ["status"])
    op.create_table(
        "eval_run_items",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "run_id",
            sa.String(length=36),
            sa.ForeignKey("eval_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("config_index", sa.Integer(), nullable=False),
        sa.Column("question_id", sa.String(length=64), nullable=False),
        sa.Column("category", sa.String(length=32), nullable=False),
        sa.Column("item_status", sa.String(length=16), nullable=False),
        sa.Column("resolution_source", sa.String(length=16), nullable=False),
        sa.Column("relocated", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("best_rank", sa.Integer(), nullable=True),
        sa.Column("recall_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("ndcg", sa.Float(), nullable=True),
        sa.Column("retrieved_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("gold_matched_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("citations_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("durations_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("idx_eval_run_items_run_id", "eval_run_items", ["run_id"])
    op.create_index("idx_eval_run_items_status", "eval_run_items", ["item_status"])


def downgrade() -> None:
    op.drop_index("idx_eval_run_items_status", table_name="eval_run_items")
    op.drop_index("idx_eval_run_items_run_id", table_name="eval_run_items")
    op.drop_table("eval_run_items")
    op.drop_index("idx_eval_runs_status", table_name="eval_runs")
    op.drop_index("idx_eval_runs_dataset_id", table_name="eval_runs")
    op.drop_table("eval_runs")
    op.drop_table("eval_datasets")
