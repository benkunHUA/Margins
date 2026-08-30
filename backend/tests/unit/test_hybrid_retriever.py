"""混合检索测试：dense + sparse → RRF 融合。"""

from uuid import uuid4

from app.core.config import RetrievalConfig
from app.domain.entities import Chunk
from app.services.embedding import EmbeddingService
from app.services.rag.hybrid_retriever import HybridRetriever
from app.vector.base import ScoredChunk, SparseIndex, VectorRepository
from app.vector.fusion import RRFFusion


class FakeEmbeddings(EmbeddingService):
    async def embed_query(self, text):
        return [1.0, 0.0]

    async def embed_texts(self, texts):
        return [[1.0, 0.0]] * len(texts)


def _chunk(text: str) -> Chunk:
    return Chunk(id=uuid4(), document_id=uuid4(), chunk_index=0, content=text)


class DenseVector(VectorRepository):
    def __init__(self, chunks):
        self.chunks = chunks

    async def search(self, embedding, k):
        return [ScoredChunk(chunk=c, score=0.9 - i * 0.1) for i, c in enumerate(self.chunks)]

    async def add(self, items):
        pass

    async def rebuild(self, chunks):
        pass

    async def save(self):
        pass

    async def load(self):
        pass


class Sparse(SparseIndex):
    def __init__(self, chunks):
        self.chunks = chunks

    async def rebuild(self, chunks):
        pass

    async def search(self, query, k):
        return [ScoredChunk(chunk=c, score=0.0) for c in reversed(self.chunks)]


def _config(**overrides) -> RetrievalConfig:
    defaults = dict(dense_k=30, sparse_k=30, rrf_k=60, fusion_top_n=30, relevance_threshold=0.3)
    defaults.update(overrides)
    return RetrievalConfig(**defaults)


async def test_hybrid_fuses_dense_and_sparse() -> None:
    a = _chunk("违约 合同")
    b = _chunk("仲裁 条款")
    hybrid = HybridRetriever(
        DenseVector([a, b]),
        Sparse([a, b]),
        FakeEmbeddings(),
        RRFFusion(),
        _config(),
    )
    results = await hybrid.retrieve("q")
    assert results[0].chunk.id == a.id  # 两路共有的 a 融合分最高
    assert {item.chunk.id for item in results} == {a.id, b.id}


async def test_hybrid_threshold_filters_dense() -> None:
    a = _chunk("高相关")
    b = _chunk("低相关")

    async def search(embedding, k):
        return [ScoredChunk(chunk=a, score=0.9), ScoredChunk(chunk=b, score=0.1)]

    hybrid = HybridRetriever(
        type("V", (), {"search": lambda self, embedding, k: search(embedding, k)})(),
        Sparse([]),
        FakeEmbeddings(),
        RRFFusion(),
        _config(relevance_threshold=0.3),
    )
    results = await hybrid.retrieve("q")
    assert all(item.chunk.id == a.id for item in results)


async def test_hybrid_logs_event(caplog) -> None:
    a = _chunk("违约 合同")
    hybrid = HybridRetriever(
        DenseVector([a]),
        Sparse([a]),
        FakeEmbeddings(),
        RRFFusion(),
        _config(),
    )
    with caplog.at_level("INFO", logger="app.services.rag.hybrid_retriever"):
        await hybrid.retrieve("q")
    assert any(
        getattr(record, "extra_fields", {}).get("event") == "hybrid"
        for record in caplog.records
    )
