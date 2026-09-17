"""SQLite 索引后端测试：契约 + 事务回滚 + 中文分词 + scope 过滤。"""

from uuid import uuid4

import pytest

from app.index.ports import IndexChangeSet, IndexRecord, RetrievalScope
from app.index.sqlite_backend import SqliteIndexBackend
from app.repositories.sql.database import run_migrations
from tests.index.contract import run_backend_contract

DIMENSION = 4


def _record(
    doc_id,
    content: str,
    embedding: list[float],
    *,
    chunk_index: int = 0,
) -> IndexRecord:
    return IndexRecord(
        chunk_id=uuid4(),
        document_id=doc_id,
        content=content,
        embedding=embedding,
        chunk_index=chunk_index,
        metadata={"doc_title": "a.pdf"},
    )


@pytest.fixture
def backend(tmp_path) -> SqliteIndexBackend:
    # 索引表结构由迁移创建（chunks / chunk_fts / index_seq），vec0 由后端按维度创建
    run_migrations(tmp_path)
    return SqliteIndexBackend(tmp_path / "margins.db", dimension=DIMENSION)


async def test_backend_satisfies_contract(backend) -> None:
    await run_backend_contract(backend)


async def test_scope_filters_dense_and_sparse(backend) -> None:
    await backend.initialize()
    doc_a, doc_b = uuid4(), uuid4()
    await backend.apply(
        IndexChangeSet(
            upserts=[
                _record(doc_a, "回购股份进展 707,939 股", [1.0, 0.0, 0.0, 0.0]),
                _record(doc_b, "公司章程 股本结构", [0.0, 1.0, 0.0, 0.0]),
            ]
        )
    )
    scope = RetrievalScope(document_ids=(doc_b,))
    dense = await backend.dense.search([1.0, 0.0, 0.0, 0.0], 5, scope)
    sparse = await backend.sparse.search("章程", 5, scope)
    assert all(item.chunk.document_id == doc_b for item in dense)
    assert all(item.chunk.document_id == doc_b for item in sparse)
    assert dense and sparse  # 范围外的召回仍能命中范围内的文档
    await backend.close()


async def test_apply_failure_rolls_back_all_tables(backend) -> None:
    await backend.initialize()
    bad = _record(uuid4(), "内容", [1.0, 0.0, 0.0])  # 维度错误 -> 写 vec 表失败
    with pytest.raises(ValueError):
        await backend.apply(IndexChangeSet(upserts=[bad]))
    stats = await backend.stats()
    assert stats == {"chunks": 0, "fts": 0, "vectors": 0}
    await backend.close()


async def test_reindex_same_document_replaces_chunks(backend) -> None:
    """重复入库（重解析）必须替换旧块，而不是叠加。"""
    await backend.initialize()
    doc_id = uuid4()
    await backend.apply(
        IndexChangeSet(upserts=[_record(doc_id, "旧内容：注册资本", [1.0, 0.0, 0.0, 0.0])])
    )
    await backend.apply(
        IndexChangeSet(
            delete_documents=[doc_id],
            upserts=[
                _record(doc_id, "新内容：回购 707,939 股", [1.0, 0.0, 0.0, 0.0], chunk_index=0),
                _record(doc_id, "新内容二：回购期限 12 个月", [0.9, 0.1, 0.0, 0.0], chunk_index=1),
            ],
        )
    )
    stats = await backend.stats()
    assert stats == {"chunks": 2, "fts": 2, "vectors": 2}
    assert await backend.sparse.search("注册资本", 5) == []
    hits = await backend.sparse.search("回购 期限", 5)
    assert hits and hits[0].chunk.chunk_index == 1
    await backend.close()


async def test_chinese_two_char_query_hits_via_jieba(backend) -> None:
    await backend.initialize()
    doc_id = uuid4()
    await backend.apply(
        IndexChangeSet(
            upserts=[
                _record(
                    doc_id,
                    "杭州安旭生物科技股份有限公司关于股份回购进展公告",
                    [1.0, 0.0, 0.0, 0.0],
                )
            ]
        )
    )
    hits = await backend.sparse.search("回购进展", 5)
    assert hits and "回购进展" in hits[0].chunk.content
    await backend.close()


async def test_initialize_reports_dimension_mismatch(tmp_path) -> None:
    run_migrations(tmp_path)
    db_path = tmp_path / "margins.db"
    first = SqliteIndexBackend(db_path, dimension=DIMENSION)
    await first.initialize()
    await first.close()

    other = SqliteIndexBackend(db_path, dimension=1024)
    with pytest.raises(RuntimeError, match="向量维度不一致"):
        await other.initialize()
