"""Embedding 服务测试（注入 fake client，不触网）。"""

from app.core.config import ModelConfig
from app.services.embedding import DashScopeEmbeddingService


class FakeEmbeddingsClient:
    def __init__(self) -> None:
        self.embedded_docs: list[list[str]] = []
        self.embedded_queries: list[str] = []

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        self.embedded_docs.append(texts)
        return [[float(ord(c)) for c in text[:2]] for text in texts]

    def embed_query(self, text: str) -> list[float]:
        self.embedded_queries.append(text)
        return [float(ord(c)) for c in text[:2]]


def _service() -> tuple[DashScopeEmbeddingService, FakeEmbeddingsClient]:
    client = FakeEmbeddingsClient()
    config = ModelConfig(dashscope_api_key="test", embedding_model="text-embedding-v4")
    return DashScopeEmbeddingService(config, client=client), client


async def test_embed_texts_batches_by_16() -> None:
    service, client = _service()
    texts = [f"t{i}" for i in range(20)]
    vectors = await service.embed_texts(texts)
    assert len(vectors) == 20
    assert client.embedded_docs == [texts[:16], texts[16:]]


async def test_embed_texts_empty_returns_empty() -> None:
    service, client = _service()
    assert await service.embed_texts([]) == []
    assert client.embedded_docs == []


async def test_embed_query() -> None:
    service, client = _service()
    vector = await service.embed_query("问题")
    assert client.embedded_queries == ["问题"]
    assert vector == [float(ord("问")), float(ord("题"))]
