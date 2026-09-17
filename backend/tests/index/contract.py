"""索引后端契约测试：每个 `IndexBackendPort` 实现都必须通过。"""

from uuid import uuid4

from app.index.ports import IndexBackendPort, IndexChangeSet, IndexRecord, RetrievalScope


async def run_backend_contract(backend: IndexBackendPort) -> None:
    await backend.initialize()
    doc_a, doc_b = uuid4(), uuid4()
    records = [
        IndexRecord(
            chunk_id=uuid4(),
            document_id=doc_a,
            content="回购股份进展：累计回购 707,939 股",
            embedding=[1.0, 0.0, 0.0, 0.0],
            metadata={"doc_title": "a.pdf"},
        ),
        IndexRecord(
            chunk_id=uuid4(),
            document_id=doc_b,
            content="公司章程：注册资本与股本结构",
            embedding=[0.0, 1.0, 0.0, 0.0],
            metadata={"doc_title": "b.pdf"},
        ),
    ]
    await backend.apply(IndexChangeSet(upserts=records))

    dense = await backend.dense.search([1.0, 0.0, 0.0, 0.0], k=5)
    assert dense and dense[0].chunk.id == records[0].chunk_id

    scoped = await backend.dense.search(
        [1.0, 0.0, 0.0, 0.0], k=5, scope=RetrievalScope(document_ids=(doc_b,))
    )
    assert scoped and all(item.chunk.document_id == doc_b for item in scoped)

    sparse = await backend.sparse.search("回购 进展", k=5)
    assert sparse and sparse[0].chunk.id == records[0].chunk_id

    sparse_scoped = await backend.sparse.search(
        "回购 进展", k=5, scope=RetrievalScope(document_ids=(doc_b,))
    )
    assert all(item.chunk.document_id == doc_b for item in sparse_scoped)

    await backend.apply(IndexChangeSet(delete_chunk_ids=[records[0].chunk_id]))
    assert all(
        item.chunk.id != records[0].chunk_id
        for item in await backend.dense.search([1.0, 0.0, 0.0, 0.0], k=5)
    )

    await backend.apply(IndexChangeSet(delete_documents=[doc_b]))
    assert await backend.sparse.search("章程", k=5) == []
    await backend.close()
