"""Faiss 向量仓库：原生 faiss IndexFlatIP + id_map.json 落盘。

与详细设计一致：chunk UUID 作向量 id、本地落盘、rebuild 收敛删除。
实现上直接用 faiss 原生 API，避免 langchain FAISS 的 Embeddings 适配层。
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Sequence

import faiss
import numpy as np

from app.core.config import StorageConfig
from app.domain.entities import Chunk
from app.services.embedding import EmbeddingService
from app.vector.base import IndexableChunk, ScoredChunk, VectorRepository


class FaissVectorRepository(VectorRepository):
    def __init__(
        self,
        config: StorageConfig,
        embeddings: EmbeddingService,
        dimension: int,
    ) -> None:
        self._config = config
        self._embeddings = embeddings
        self._dim = dimension
        self._index: faiss.IndexFlatIP | None = None
        self._id_map: dict[int, str] = {}
        self._chunks: dict[str, Chunk] = {}
        self._lock = asyncio.Lock()
        self._index_file = config.faiss_index_dir / "index.faiss"
        self._map_file = config.faiss_index_dir / "id_map.json"

    @staticmethod
    def _normalize(vector: Sequence[float]) -> np.ndarray:
        arr = np.asarray(vector, dtype="float32")
        norm = np.linalg.norm(arr)
        return arr if norm == 0 else arr / norm

    def _save_sync(self) -> None:
        if self._index is None:
            return
        self._config.faiss_index_dir.mkdir(parents=True, exist_ok=True)
        faiss.write_index(self._index, str(self._index_file))
        payload = {
            str(idx): {
                "chunk_id": chunk_id,
                "chunk": self._chunks[chunk_id].model_dump(mode="json"),
            }
            for idx, chunk_id in self._id_map.items()
        }
        self._map_file.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    def _search_sync(self, embedding: Sequence[float], k: int) -> list[ScoredChunk]:
        if self._index is None or self._index.ntotal == 0:
            return []
        query = self._normalize(embedding).reshape(1, -1)
        scores, idxs = self._index.search(query, k)
        results: list[ScoredChunk] = []
        for score, idx in zip(scores[0], idxs[0], strict=True):
            if idx < 0:
                continue
            chunk_id = self._id_map.get(int(idx))
            chunk = self._chunks.get(chunk_id or "")
            if chunk is not None:
                results.append(ScoredChunk(chunk=chunk, score=float(score)))
        return results

    async def add(self, items: Sequence[IndexableChunk]) -> None:
        async with self._lock:
            def _do() -> None:
                if self._index is None:
                    self._index = faiss.IndexFlatIP(self._dim)
                vectors = np.vstack([self._normalize(item.embedding) for item in items])
                start = self._index.ntotal
                self._index.add(vectors)
                for offset, item in enumerate(items):
                    chunk_id = str(item.chunk.id)
                    self._id_map[start + offset] = chunk_id
                    self._chunks[chunk_id] = item.chunk
                self._save_sync()

            await asyncio.to_thread(_do)

    async def search(self, embedding: Sequence[float], k: int) -> list[ScoredChunk]:
        return await asyncio.to_thread(self._search_sync, embedding, k)

    async def rebuild(self, chunks: Sequence[Chunk]) -> None:
        async with self._lock:
            embeddings = await self._embeddings.embed_texts([c.content for c in chunks])

            def _do() -> None:
                index = faiss.IndexFlatIP(self._dim)
                id_map: dict[int, str] = {}
                chunks_map: dict[str, Chunk] = {}
                for i, (chunk, embedding) in enumerate(zip(chunks, embeddings, strict=True)):
                    index.add(self._normalize(embedding).reshape(1, -1))
                    id_map[i] = str(chunk.id)
                    chunks_map[str(chunk.id)] = chunk
                self._index = index
                self._id_map = id_map
                self._chunks = chunks_map
                self._save_sync()

            await asyncio.to_thread(_do)

    async def save(self) -> None:
        await asyncio.to_thread(self._save_sync)

    async def load(self) -> None:
        async with self._lock:
            def _do() -> None:
                if not self._index_file.exists():
                    return
                self._index = faiss.read_index(str(self._index_file))
                payload = json.loads(self._map_file.read_text(encoding="utf-8"))
                self._id_map = {int(idx): item["chunk_id"] for idx, item in payload.items()}
                self._chunks = {
                    item["chunk_id"]: Chunk.model_validate(item["chunk"])
                    for item in payload.values()
                }

            await asyncio.to_thread(_do)
