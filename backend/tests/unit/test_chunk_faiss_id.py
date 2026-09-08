"""Chunk 仓储 faiss_id 分配/回查测试（内存 + SQL）。"""

from pathlib import Path
from uuid import uuid4

from app.domain.entities import Chunk, Document
from app.repositories.memory.memory_repos import InMemoryChunkRepository
from app.repositories.sql.chunks import ChunkSqlRepository
from app.repositories.sql.database import create_engine_and_sessionmaker, init_db
from app.repositories.sql.documents import DocumentSqlRepository


def _chunks(n: int) -> list[Chunk]:
    return _chunks_for(uuid4(), n)


def _chunks_for(doc_id, n: int) -> list[Chunk]:
    return [
        Chunk(document_id=doc_id, chunk_index=i, content=f"内容{i}") for i in range(n)
    ]


async def test_memory_assigns_monotonic_ids() -> None:
    repo = InMemoryChunkRepository()
    first = _chunks(2)
    second = _chunks(2)
    await repo.add_many(first)
    await repo.add_many(second)
    ids = [c.faiss_id for c in first + second]
    assert len(set(ids)) == 4
    assert max(ids) == min(ids) + 3


async def test_sql_assigns_from_sequence(tmp_path) -> None:
    engine, session_factory = create_engine_and_sessionmaker(tmp_path)
    await init_db(engine)
    repo = ChunkSqlRepository(session_factory)
    try:
        documents = DocumentSqlRepository(session_factory)
        doc1 = await documents.create(_doc("d1"))
        doc2 = await documents.create(_doc("d2"))
        await _assert_assignment_and_lookup_for(repo, doc1.id)
        await _assert_assignment_and_lookup_for(repo, doc2.id)  # 第二批号码继续递增
    finally:
        await engine.dispose()


async def test_sql_backfills_missing_ids(tmp_path) -> None:
    from sqlalchemy import insert

    from app.repositories.sql.models import ChunkRow

    engine, session_factory = create_engine_and_sessionmaker(tmp_path)
    await init_db(engine)
    repo = ChunkSqlRepository(session_factory)
    try:
        documents = DocumentSqlRepository(session_factory)
        doc = await documents.create(_doc("d"))
        async with session_factory() as session:
            await session.execute(
                insert(ChunkRow).values(
                    id=str(uuid4()),
                    document_id=str(doc.id),
                    chunk_index=0,
                    content="旧数据",
                    metadata_json="{}",
                )
            )
            await session.commit()

        count = await repo.allocate_missing_ids()
        assert count == 1
        rows = await repo.list_all()
        assert rows[0].faiss_id is not None
    finally:
        await engine.dispose()


def _doc(filename: str) -> Document:
    return Document(
        filename=filename,
        file_type="pdf",
        file_size=1,
        file_path=Path(__file__),
    )


async def _assert_assignment_and_lookup_for(repo, doc_id) -> None:
    chunks = _chunks_for(doc_id, 3)
    await repo.add_many(chunks)

    assert all(c.faiss_id is not None for c in chunks)
    assert len({c.faiss_id for c in chunks}) == 3

    rows = [r for r in await repo.list_all() if r.document_id == doc_id]
    assert {c.faiss_id for c in rows} == {c.faiss_id for c in chunks}

    fetched = await repo.get_by_faiss_ids([c.faiss_id for c in chunks[:2]])
    assert {c.id for c in fetched} == {c.id for c in chunks[:2]}
