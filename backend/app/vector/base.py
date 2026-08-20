"""向量库与稀疏索引接口。"""

from abc import ABC, abstractmethod
from collections.abc import Sequence

from pydantic import BaseModel

from app.domain.entities import Chunk


class IndexableChunk(BaseModel):
    chunk: Chunk
    embedding: list[float]


class ScoredChunk(BaseModel):
    chunk: Chunk
    score: float


class VectorRepository(ABC):
    """稠密向量索引（Faiss 实现见 faiss_repo.py，M1 落地）。"""

    @abstractmethod
    async def add(self, items: Sequence[IndexableChunk]) -> None: ...

    @abstractmethod
    async def search(self, embedding: list[float], k: int) -> list[ScoredChunk]: ...

    @abstractmethod
    async def rebuild(self, chunks: Sequence[Chunk]) -> None: ...

    @abstractmethod
    async def save(self) -> None: ...

    @abstractmethod
    async def load(self) -> None: ...


class SparseIndex(ABC):
    """稀疏索引（BM25 实现见 sparse.py，M1 落地）。"""

    @abstractmethod
    async def rebuild(self, chunks: Sequence[Chunk]) -> None: ...

    @abstractmethod
    async def search(self, query: str, k: int) -> list[ScoredChunk]: ...
