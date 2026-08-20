"""BM25 稀疏索引（M1 落地，基于 langchain-community BM25Retriever）。"""

from collections.abc import Sequence

from app.core.exceptions import NotImplementedStageError
from app.domain.entities import Chunk
from app.vector.base import ScoredChunk, SparseIndex


class BM25SparseIndex(SparseIndex):
    def __init__(self) -> None:
        self._retriever = None  # M1: BM25Retriever

    async def rebuild(self, chunks: Sequence[Chunk]) -> None:
        raise NotImplementedStageError("M1: BM25 语料重建")

    async def search(self, query: str, k: int) -> list[ScoredChunk]:
        raise NotImplementedStageError("M1: BM25 检索")
