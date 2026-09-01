"""Embedding 服务：阿里云百炼 text-embedding-v4（dashscope SDK 直连，分批 + 令牌桶限速）。"""

import asyncio
from abc import ABC, abstractmethod
from collections.abc import Sequence

import dashscope

from app.core.config import ModelConfig
from app.core.exceptions import EmbeddingError
from app.utils.rate_limit import AsyncTokenBucket


class EmbeddingService(ABC):
    @abstractmethod
    async def embed_texts(self, texts: Sequence[str]) -> list[list[float]]: ...

    @abstractmethod
    async def embed_query(self, text: str) -> list[float]: ...


class DashScopeEmbeddingService(EmbeddingService):
    """call 可注入替身（测试）；默认 dashscope.TextEmbedding.call。"""

    def __init__(self, config: ModelConfig, call=None) -> None:
        self._config = config
        self._call = call or dashscope.TextEmbedding.call
        self._bucket = AsyncTokenBucket(rate=20, capacity=20)

    async def embed_texts(self, texts: Sequence[str]) -> list[list[float]]:
        if not texts:
            return []
        results: list[list[float]] = []
        for start in range(0, len(texts), 16):
            batch = list(texts[start : start + 16])
            await self._bucket.acquire(len(batch))
            response = await asyncio.to_thread(
                self._call,
                model=self._config.embedding_model,
                input=batch,
                api_key=self._config.dashscope_api_key,
                dimension=self._config.embedding_dimension,
            )
            results.extend(_parse_embeddings(response, len(batch)))
        return results

    async def embed_query(self, text: str) -> list[float]:
        await self._bucket.acquire()
        response = await asyncio.to_thread(
            self._call,
            model=self._config.embedding_model,
            input=text,
            api_key=self._config.dashscope_api_key,
            dimension=self._config.embedding_dimension,
        )
        return _parse_embeddings(response, 1)[0]


def _field(obj, name, default=None):
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _parse_embeddings(response, expected: int) -> list[list[float]]:
    output = _field(response, "output")
    items = _field(output, "embeddings")
    if not items:
        status = _field(response, "status_code", "") or ""
        code = _field(response, "code", "") or ""
        message = _field(response, "message", "") or ""
        detail = (
            f"status={status}, code={code}, message={message}"
            if (status or code or message)
            else "响应为空"
        )
        raise EmbeddingError(f"embedding 调用失败: {detail}")
    ordered = sorted(items, key=lambda item: int(_field(item, "text_index", 0)))
    vectors = [list(_field(item, "embedding", [])) for item in ordered]
    if len(vectors) < expected:
        raise EmbeddingError(f"embedding 数量不足: {len(vectors)} < {expected}")
    return vectors[:expected]
