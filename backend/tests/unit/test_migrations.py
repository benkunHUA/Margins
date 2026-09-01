"""Alembic 迁移测试：临时库执行 upgrade head 后表结构齐全。"""

import logging

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
