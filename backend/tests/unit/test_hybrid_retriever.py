"""混合检索测试：dense + sparse → RRF 融合 + 检索范围透传。"""

from uuid import uuid4

from app.core.config import RetrievalConfig
from app.domain.entities import Chunk
from app.index.fusion import RRFFusion
from app.index.ports import IndexChangeSet, IndexRecord, RetrievalScope
from app.services.embedding import EmbeddingService
from app.services.rag.hybrid_retriever import HybridRetriever
from tests.index.fakes import InMemoryIndexBackend, StubIndexBackend


class FakeEmbeddings(EmbeddingService):
    async def embed_query(self, text):
        return [1.0, 0.0]

    async def embed_texts(self, texts):
        return [[1.0, 0.0]] * len(texts)


def _chunk(text: str) -> Chunk:
    return Chunk(id=uuid4(), document_id=uuid4(), chunk_index=0, content=text)


def _config(**overrides) -> RetrievalConfig:
    defaults = dict(recall_k=30, relevance_threshold=0.3)
    defaults.update(overrides)
    return RetrievalConfig(**defaults)


async def test_hybrid_fuses_dense_and_sparse() -> None:
    a = _chunk("违约 合同")
    b = _chunk("仲裁 条款")
    hybrid = HybridRetriever(
        StubIndexBackend([a, b], [a, b]),
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

    hybrid = HybridRetriever(
        StubIndexBackend([a, b], [], dense_scores=[0.9, 0.1]),
        FakeEmbeddings(),
        RRFFusion(),
        _config(relevance_threshold=0.3),
    )
    results = await hybrid.retrieve("q")
    assert all(item.chunk.id == a.id for item in results)


async def test_hybrid_logs_event(caplog) -> None:
    a = _chunk("违约 合同")
    hybrid = HybridRetriever(
        StubIndexBackend([a], [a]),
        FakeEmbeddings(),
        RRFFusion(),
        _config(),
    )
    with caplog.at_level("INFO", logger="app.services.rag.hybrid_retriever"):
        await hybrid.retrieve("q")
    hybrid_log = next(
        record for record in caplog.records
        if getattr(record, "extra_fields", {}).get("event") == "hybrid"
    )
    assert hybrid_log.extra_fields["results"][0]["chunk_id"] == str(a.id)


async def test_hybrid_passes_scope_down_to_backend() -> None:
    """@ 文档提问的范围过滤必须下推给索引层，而不是取回全量再筛。"""
    backend = StubIndexBackend([_chunk("在范围外")], [_chunk("在范围内")])
    hybrid = HybridRetriever(backend, FakeEmbeddings(), RRFFusion(), _config())
    doc_id = uuid4()

    await hybrid.retrieve("q", scope=RetrievalScope(document_ids=(doc_id,)))

    expected = RetrievalScope(document_ids=(doc_id,))
    assert backend.dense.scopes == [expected]
    assert backend.sparse.scopes == [expected]


async def test_hybrid_scope_filters_results_with_real_backend() -> None:
    backend = InMemoryIndexBackend()
    doc_a, doc_b = uuid4(), uuid4()
    await backend.apply(
        IndexChangeSet(
            upserts=[
                IndexRecord(
                    chunk_id=uuid4(),
                    document_id=doc_a,
                    content="回购股份进展",
                    embedding=[1.0, 0.0],
                ),
                IndexRecord(
                    chunk_id=uuid4(),
                    document_id=doc_b,
                    content="公司章程",
                    embedding=[1.0, 0.0],
                ),
            ]
        )
    )
    hybrid = HybridRetriever(backend, FakeEmbeddings(), RRFFusion(), _config())

    results = await hybrid.retrieve("回购", scope=RetrievalScope(document_ids=(doc_b,)))

    assert results
    assert all(item.chunk.document_id == doc_b for item in results)
