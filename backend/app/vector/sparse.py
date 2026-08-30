"""BM25 稀疏索引（rank_bm25 直连，进程内内存语料）。"""

import asyncio
import re
from collections.abc import Sequence

from rank_bm25 import BM25Okapi

from app.domain.entities import Chunk
from app.vector.base import ScoredChunk, SparseIndex


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[\w\u4e00-\u9fff]+", text.lower())


class BM25SparseIndex(SparseIndex):
    def __init__(self) -> None:
        self._chunks: list[Chunk] = []
        self._bm25: BM25Okapi | None = None

    async def rebuild(self, chunks: Sequence[Chunk]) -> None:
        def _do() -> None:
            self._chunks = list(chunks)
            self._bm25 = (
                BM25Okapi([_tokenize(c.content) for c in chunks]) if chunks else None
            )

        await asyncio.to_thread(_do)

    async def search(self, query: str, k: int) -> list[ScoredChunk]:
        if self._bm25 is None or not self._chunks:
            return []

        def _do() -> list[ScoredChunk]:
            scores = self._bm25.get_scores(_tokenize(query))
            indexes = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:k]
            return [
                ScoredChunk(chunk=self._chunks[i], score=float(scores[i]))
                for i in indexes
                if scores[i] > 0
            ]

        return await asyncio.to_thread(_do)
