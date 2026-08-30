"""Embedding 服务测试（注入 fake call，不触网）。"""

from app.core.config import ModelConfig
from app.services.embedding import DashScopeEmbeddingService


def _fake_call(model, input, **kwargs):
    texts = input if isinstance(input, list) else [input]
    return {
        "output": {
            "embeddings": [
                {"text_index": i, "embedding": [float(i + 1), 0.0]}
                for i in range(len(texts))
            ]
        }
    }


def _service() -> tuple[DashScopeEmbeddingService, list]:
    calls: list = []

    def call(model, input, **kwargs):
        calls.append(input)
        return _fake_call(model, input, **kwargs)

    config = ModelConfig(
        dashscope_api_key="test",
        embedding_model="text-embedding-v4",
        embedding_dimension=2,
    )
    return DashScopeEmbeddingService(config, call=call), calls


async def test_embed_texts_batches_by_16() -> None:
    service, calls = _service()
    texts = [f"t{i}" for i in range(20)]
    vectors = await service.embed_texts(texts)
    assert len(vectors) == 20
    assert calls == [texts[:16], texts[16:]]
    assert vectors[0] == [1.0, 0.0]


async def test_embed_texts_empty_returns_empty() -> None:
    service, calls = _service()
    assert await service.embed_texts([]) == []
    assert calls == []


async def test_embed_query() -> None:
    service, calls = _service()
    vector = await service.embed_query("问题")
    assert calls == ["问题"]
    assert vector == [1.0, 0.0]
