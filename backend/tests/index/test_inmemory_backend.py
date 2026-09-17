"""契约先行：先让内存实现跑通契约，再用同一套断言约束 SQLite 实现。"""

from uuid import uuid4

from app.index.ports import IndexChangeSet, IndexRecord
from tests.index.contract import run_backend_contract
from tests.index.fakes import InMemoryIndexBackend


async def test_inmemory_backend_satisfies_contract() -> None:
    await run_backend_contract(InMemoryIndexBackend())


async def test_default_search_hybrid_merges_both_legs() -> None:
    backend = InMemoryIndexBackend()
    doc_id = uuid4()
    await backend.apply(
        IndexChangeSet(
            upserts=[
                IndexRecord(
                    chunk_id=uuid4(),
                    document_id=doc_id,
                    content="回购股份进展",
                    embedding=[1.0, 0.0, 0.0, 0.0],
                )
            ]
        )
    )
    fused = await backend.search_hybrid(
        "回购", [1.0, 0.0, 0.0, 0.0], k=5
    )
    # 未传 fusion 时退化为两路直接拼接：同一 chunk 出现两次，但两路都命中了。
    assert len(fused) == 2
