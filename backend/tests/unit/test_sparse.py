"""BM25 稀疏索引测试（真实 BM25，本地语料）。"""

from uuid import uuid4

from app.domain.entities import Chunk
from app.vector.sparse import BM25SparseIndex


def _chunk(text: str) -> Chunk:
    return Chunk(id=uuid4(), document_id=uuid4(), chunk_index=0, content=text)


async def test_rebuild_and_search() -> None:
    index = BM25SparseIndex()
    chunks = [
        _chunk("违约责任 违约金 合同"),
        _chunk("仲裁 争议解决 条款"),
        _chunk("税务 申报 发票"),
    ]
    await index.rebuild(chunks)

    results = await index.search("违约金", k=1)
    assert len(results) == 1
    assert "违约" in results[0].chunk.content


async def test_empty_index_returns_empty() -> None:
    index = BM25SparseIndex()
    await index.rebuild([])
    assert await index.search("q", k=5) == []
