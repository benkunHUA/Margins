"""SQLAlchemy async 数据库基础设施（SQLite + aiosqlite，WAL + 外键）。"""

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.repositories.sql.models import Base

BACKEND_DIR = Path(__file__).resolve().parents[3]


@event.listens_for(Engine, "connect")
def _enable_sqlite_foreign_keys(dbapi_connection, _connection_record) -> None:
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.close()


def create_engine_and_sessionmaker(
    data_dir: Path,
) -> tuple[AsyncEngine, async_sessionmaker[AsyncSession]]:
    db_path = data_dir / "margins.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}", echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    return engine, session_factory


async def init_db(engine: AsyncEngine) -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


def run_migrations(data_dir: Path) -> None:
    """对指定数据目录执行 Alembic upgrade head（同步，调用方放线程）。"""
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", f"sqlite:///{data_dir / 'margins.db'}")
    command.upgrade(cfg, "head")
