"""Alembic 迁移测试：临时库执行 upgrade head 后表结构齐全。"""

import logging

import sqlalchemy as sa
from sqlalchemy import create_engine, inspect

from app.repositories.sql.database import run_migrations


def test_migrations_create_all_tables(tmp_path) -> None:
    run_migrations(tmp_path)
    engine = create_engine(f"sqlite:///{tmp_path / 'margins.db'}")
    tables = set(inspect(engine).get_table_names())
    assert {
        "documents",
        "chunks",
        "sessions",
        "messages",
        "parse_jobs",
        "query_logs",
        "alembic_version",
    } <= tables
    engine.dispose()


def test_migrations_do_not_touch_logging(tmp_path) -> None:
    root = logging.getLogger()
    old_level = root.level
    old_handlers = list(root.handlers)

    run_migrations(tmp_path)

    assert root.level == old_level
    assert root.handlers == old_handlers


def test_migration_0003_adds_parse_mode_column(tmp_path) -> None:
    run_migrations(tmp_path)
    engine = create_engine(f"sqlite:///{tmp_path / 'margins.db'}")
    columns = {c["name"] for c in inspect(engine).get_columns("documents")}
    assert "parse_mode" in columns
    engine.dispose()


def test_migration_0004_adds_faiss_id_and_seq(tmp_path) -> None:
    run_migrations(tmp_path)
    engine = create_engine(f"sqlite:///{tmp_path / 'margins.db'}")
    chunk_cols = {c["name"] for c in inspect(engine).get_columns("chunks")}
    assert "faiss_id" in chunk_cols
    tables = set(inspect(engine).get_table_names())
    assert "faiss_seq" in tables
    with engine.connect() as conn:
        value = conn.execute(
            sa.text("SELECT next_id FROM faiss_seq WHERE id=1")
        ).scalar_one()
        assert value == 0
    engine.dispose()


def test_migration_0005_creates_eval_tables(tmp_path) -> None:
    run_migrations(tmp_path)
    engine = create_engine(f"sqlite:///{tmp_path / 'margins.db'}")
    tables = set(inspect(engine).get_table_names())
    assert {"eval_datasets", "eval_runs", "eval_run_items"} <= tables
    engine.dispose()


def test_migration_0006_adds_item_detail_columns(tmp_path) -> None:
    run_migrations(tmp_path)
    engine = create_engine(f"sqlite:///{tmp_path / 'margins.db'}")
    columns = {c["name"] for c in inspect(engine).get_columns("eval_run_items")}
    assert {"question", "diagnostics_json"} <= columns
    engine.dispose()
