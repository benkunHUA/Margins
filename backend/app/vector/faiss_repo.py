"""Faiss 向量库实现（M1 落地，基于 langchain-community FAISS 封装）。"""

from collections.abc import Sequence

from app.core.config import StorageConfig
from app.core.exceptions import NotImplementedStageError
from app.domain.entities import Chunk
from app.vector.base import IndexableChunk, ScoredChunk, VectorRepository


class FaissVectorRepository(VectorRepository):
    def __init__(self, config: StorageConfig) -> None:
        self._config = config
        self._lock = None  # M1: asyncio.Lock 串行化写入
        self._store = None  # M1: langchain_community FAISS 实例

    async def add(self, items: Sequence[IndexableChunk]) -> None:
        raise NotImplementedStageError("M1: Faiss 写入与落盘")

    async def search(self, embedding: list[float], k: int) -> list[ScoredChunk]:
        raise NotImplementedStageError("M1: Faiss 检索")

    async def rebuild(self, chunks: Sequence[Chunk]) -> None:
        raise NotImplementedStageError("M1: Faiss 重建")

    async def save(self) -> None:
        raise NotImplementedStageError("M1: Faiss 落盘")

    async def load(self) -> None:
        raise NotImplementedStageError("M1: Faiss 加载")
