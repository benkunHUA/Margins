"""Alembic 迁移测试：临时库执行 upgrade head 后表结构齐全。"""

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
