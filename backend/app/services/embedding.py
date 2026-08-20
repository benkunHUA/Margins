"""Embedding 服务：阿里云百炼 text-embedding-v4。"""

from abc import ABC, abstractmethod
from collections.abc import Sequence

from app.core.config import ModelConfig
from app.core.exceptions import NotImplementedStageError


class EmbeddingService(ABC):
    @abstractmethod
    async def embed_texts(self, texts: Sequence[str]) -> list[list[float]]: ...

    @abstractmethod
    async def embed_query(self, text: str) -> list[float]: ...


class DashScopeEmbeddingService(EmbeddingService):
    """基于 langchain-community DashScopeEmbeddings（M1 落地，分批 + 令牌桶限速）。"""

    def __init__(self, config: ModelConfig) -> None:
        self._config = config
        self._embeddings = None  # M1: DashScopeEmbeddings(model=text-embedding-v4)
        self._bucket = None  # M1: AsyncTokenBucket

    async def embed_texts(self, texts: Sequence[str]) -> list[list[float]]:
        raise NotImplementedStageError("M1: 百炼 text-embedding-v4 向量化")

    async def embed_query(self, text: str) -> list[float]:
        raise NotImplementedStageError("M1: 百炼 text-embedding-v4 查询向量化")
