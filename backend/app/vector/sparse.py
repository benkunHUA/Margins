"""BM25 稀疏索引（langchain BM25Retriever，进程内内存语料）。"""

import asyncio
from collections.abc import Sequence
from uuid import UUID

from langchain_community.retrievers import BM25Retriever

from app.domain.entities import Chunk
from app.vector.base import ScoredChunk, SparseIndex


class BM25SparseIndex(SparseIndex):
    def __init__(self) -> None:
        self._retriever: BM25Retriever | None = None

    async def rebuild(self, chunks: Sequence[Chunk]) -> None:
        def _do() -> None:
            if not chunks:
                self._retriever = None
                return
            self._retriever = BM25Retriever.from_texts(
                [c.content for c in chunks],
                metadatas=[
                    {
                        "chunk_id": str(c.id),
                        "document_id": str(c.document_id),
                        "chunk_index": c.chunk_index,
                    }
                    for c in chunks
                ],
                ids=[str(c.id) for c in chunks],
            )

        await asyncio.to_thread(_do)

    async def search(self, query: str, k: int) -> list[ScoredChunk]:
        if self._retriever is None:
            return []

        def _do() -> list[ScoredChunk]:
            self._retriever.k = k
            docs = self._retriever.invoke(query)
            results: list[ScoredChunk] = []
            for doc in docs:
                meta = doc.metadata
                results.append(
                    ScoredChunk(
                        chunk=Chunk(
                            id=UUID(meta["chunk_id"]),
                            document_id=UUID(meta["document_id"]),
                            chunk_index=meta.get("chunk_index", 0),
                            content=doc.page_content,
                        ),
                        score=0.0,
                    )
                )
            return results

        return await asyncio.to_thread(_do)
