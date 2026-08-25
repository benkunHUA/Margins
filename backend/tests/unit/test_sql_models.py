"""SQLAlchemy 表结构与级联删除测试。"""

from datetime import datetime

import pytest
from sqlalchemy import delete, func, select

from app.repositories.sql.database import create_engine_and_sessionmaker, init_db
from app.repositories.sql.models import ChunkRow, DocumentRow, ParseJobRow


@pytest.fixture
async def db(tmp_path):
    engine, session_factory = create_engine_and_sessionmaker(tmp_path)
    await init_db(engine)
    yield session_factory
    await engine.dispose()


async def test_create_all_and_roundtrip(db) -> None:
    async with db() as session:
        session.add(
            DocumentRow(
                id="doc-1",
                filename="a.pdf",
                file_type="pdf",
                file_size=10,
                file_path="/tmp/a.pdf",
                status="pending",
                created_at=datetime.now(),
                updated_at=datetime.now(),
            )
        )
        await session.commit()

    async with db() as session:
        rows = (await session.execute(select(DocumentRow))).scalars().all()
        assert len(rows) == 1
        assert rows[0].filename == "a.pdf"


async def test_document_cascade_deletes_chunks(db) -> None:
    async with db() as session:
        session.add(
            DocumentRow(
                id="doc-2",
                filename="b.md",
                file_type="md",
                file_size=5,
                file_path="/tmp/b.md",
                status="ready",
                created_at=datetime.now(),
                updated_at=datetime.now(),
            )
        )
        await session.flush()  # 先落父表，再插子表（无 ORM relationship 时按表名排序）
        session.add(ChunkRow(id="chunk-1", document_id="doc-2", chunk_index=0, content="x"))
        session.add(ParseJobRow(id="job-1", document_id="doc-2", status="succeeded"))
        await session.commit()

    async with db() as session:
        await session.execute(delete(DocumentRow).where(DocumentRow.id == "doc-2"))
        await session.commit()

    async with db() as session:
        chunks = (await session.execute(select(func.count()).select_from(ChunkRow))).scalar_one()
        jobs = (await session.execute(select(func.count()).select_from(ParseJobRow))).scalar_one()
        assert chunks == 0
        assert jobs == 1  # parse_jobs 不级联，由仓储显式处理
