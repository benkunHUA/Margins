"""重排序测试（注入 fake call，不触网）。"""

from uuid import uuid4

from app.core.config import ModelConfig
from app.domain.entities import Chunk
from app.services.reranking import DashScopeReranker
from app.vector.base import ScoredChunk


def _chunk(text: str) -> Chunk:
    return Chunk(id=uuid4(), document_id=uuid4(), chunk_index=0, content=text)


def _fake_call(model, query, documents, **kwargs):
    return {
        "output": {
            "results": [
                {"index": 1, "relevance_score": 0.95},
                {"index": 0, "relevance_score": 0.20},
            ]
        }
    }


async def test_rerank_orders_and_filters_by_threshold() -> None:
    a = _chunk("低相关")
    b = _chunk("高相关")
    reranker = DashScopeReranker(ModelConfig(rerank_model="qwen3-rerank"), call=_fake_call)
    result = await reranker.rerank(
        "q",
        [ScoredChunk(chunk=a, score=0.5), ScoredChunk(chunk=b, score=0.5)],
        top_n=2,
        threshold=0.3,
    )
    assert [item.chunk.id for item in result] == [b.id]


async def test_rerank_empty_candidates() -> None:
    reranker = DashScopeReranker(ModelConfig(rerank_model="qwen3-rerank"), call=_fake_call)
    assert await reranker.rerank("q", [], top_n=2, threshold=0.0) == []
