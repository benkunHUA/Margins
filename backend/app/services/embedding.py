"""Embedding 服务：阿里云百炼 text-embedding-v4（分批 + 令牌桶限速）。"""

import asyncio
from abc import ABC, abstractmethod
from collections.abc import Sequence

from langchain_community.embeddings import DashScopeEmbeddings

from app.core.config import ModelConfig
from app.utils.rate_limit import AsyncTokenBucket


class EmbeddingService(ABC):
    @abstractmethod
    async def embed_texts(self, texts: Sequence[str]) -> list[list[float]]: ...

    @abstractmethod
    async def embed_query(self, text: str) -> list[float]: ...


class DashScopeEmbeddingService(EmbeddingService):
    """client 可注入替身（测试）；默认走 langchain DashScopeEmbeddings。"""

    def __init__(
        self,
        config: ModelConfig,
        client: DashScopeEmbeddings | None = None,
    ) -> None:
        self._config = config
        self._client = client
        self._bucket = AsyncTokenBucket(rate=20, capacity=20)
        self._embeddings: DashScopeEmbeddings | None = None

    def _embeddings_client(self) -> DashScopeEmbeddings:
        """惰性创建：无 key 时在使用阶段报错，避免应用启动/导入即失败。"""
        if self._client is not None:
            return self._client
        if self._embeddings is None:
            self._embeddings = DashScopeEmbeddings(
                dashscope_api_key=self._config.dashscope_api_key,
                model=self._config.embedding_model,
            )
        return self._embeddings

    async def embed_texts(self, texts: Sequence[str]) -> list[list[float]]:
        if not texts:
            return []
        results: list[list[float]] = []
        for start in range(0, len(texts), 16):
            batch = list(texts[start : start + 16])
            await self._bucket.acquire(len(batch))
            vectors = await asyncio.to_thread(self._embeddings_client().embed_documents, batch)
            results.extend(vectors)
        return results

    async def embed_query(self, text: str) -> list[float]:
        await self._bucket.acquire()
        return await asyncio.to_thread(self._embeddings_client().embed_query, text)
