"""Faiss 向量仓库：IndexIDMap(IndexFlatIP)，faiss_id 直接写入二进制。

chunks.faiss_id 由 ChunkRepository 分配并持久化到 SQLite；检索后按 faiss_id
回查 chunk 原文。写盘采用临时文件 + os.replace 原子替换；不再读写 id_map.json。
"""

from __future__ import annotations

import asyncio
import os
from collections.abc import Sequence

import faiss
import numpy as np

from app.core.config import StorageConfig
from app.domain.entities import Chunk
from app.repositories.base import ChunkRepository
from app.services.embedding import EmbeddingService
from app.vector.base import IndexableChunk, ScoredChunk, VectorRepository


class FaissVectorRepository(VectorRepository):
    def __init__(
        self,
        config: StorageConfig,
        embeddings: EmbeddingService,
        dimension: int,
        chunks: ChunkRepository | None = None,
    ) -> None:
        self._config = config
        self._embeddings = embeddings
        self._dim = dimension
        self._chunks_repo = chunks
        self._index: faiss.IndexIDMap | None = None
        self._ids: set[int] = set()
        self._lock = asyncio.Lock()
        self._index_file = config.faiss_index_dir / "index.faiss"
        self._map_file = config.faiss_index_dir / "id_map.json"
        self.needs_rebuild = False

    def loaded_ids(self) -> set[int]:
        return set(self._ids)

    @staticmethod
    def _normalize(vector: Sequence[float]) -> np.ndarray:
        arr = np.asarray(vector, dtype="float32")
        norm = np.linalg.norm(arr)
        return arr if norm == 0 else arr / norm

    def _save_atomic_sync(self) -> None:
        if self._index is None:
            return
        self._config.faiss_index_dir.mkdir(parents=True, exist_ok=True)
        tmp = self._index_file.with_suffix(".faiss.tmp")
        faiss.write_index(self._index, str(tmp))
        os.replace(tmp, self._index_file)
        self._map_file.unlink(missing_ok=True)  # 清理历史 JSON

    def _search_sync(self, embedding: Sequence[float], k: int) -> list[tuple[int, float]]:
        if self._index is None or self._index.ntotal == 0:
            return []
        query = self._normalize(embedding).reshape(1, -1)
        scores, idxs = self._index.search(query, k)
        return [
            (int(fid), float(score))
            for score, fid in zip(scores[0], idxs[0], strict=True)
            if fid >= 0
        ]

    async def add(self, items: Sequence[IndexableChunk]) -> None:
        async with self._lock:
            for item in items:
                if item.chunk.faiss_id is None:
                    raise ValueError("IndexableChunk 缺少 faiss_id，先经 ChunkRepository 分配")

            def _do() -> None:
                if self._index is None:
                    self._index = faiss.IndexIDMap(faiss.IndexFlatIP(self._dim))
                vectors = np.vstack([self._normalize(item.embedding) for item in items])
                ids = np.asarray(
                    [int(item.chunk.faiss_id) for item in items], dtype="int64"
                )
                self._index.add_with_ids(vectors, ids)
                self._ids.update(int(fid) for fid in ids)
                self._save_atomic_sync()

            await asyncio.to_thread(_do)

    async def search(self, embedding: Sequence[float], k: int) -> list[ScoredChunk]:
        async with self._lock:
            hits = await asyncio.to_thread(self._search_sync, embedding, k)
            if not hits:
                return []
            faiss_ids = [fid for fid, _ in hits]
            rows = await self._chunks_repo.get_by_faiss_ids(faiss_ids)
            by_id = {row.faiss_id: row for row in rows}
            return [
                ScoredChunk(chunk=by_id[fid], score=score)
                for fid, score in hits
                if fid in by_id
            ]

    async def remove(self, faiss_ids: Sequence[int]) -> None:
        ids = [int(fid) for fid in faiss_ids if fid is not None]
        if not ids:
            return
        async with self._lock:
            def _do() -> None:
                if self._index is None:
                    return
                self._index.remove_ids(np.asarray(ids, dtype="int64"))
                self._ids.difference_update(ids)
                self._save_atomic_sync()

            await asyncio.to_thread(_do)

    async def rebuild(self, chunks: Sequence[Chunk]) -> None:
        async with self._lock:
            embeddings = await self._embeddings.embed_texts(
                [c.content for c in chunks]
            )

            def _do() -> None:
                index = faiss.IndexIDMap(faiss.IndexFlatIP(self._dim))
                ids: list[int] = []
                for chunk in chunks:
                    if chunk.faiss_id is None:
                        raise ValueError("rebuild 前需为 chunk 分配 faiss_id")
                    ids.append(int(chunk.faiss_id))
                if chunks:
                    vectors = np.vstack(
                        [self._normalize(embedding) for embedding in embeddings]
                    )
                    index.add_with_ids(vectors, np.asarray(ids, dtype="int64"))
                self._index = index
                self._ids = set(ids)
                self.needs_rebuild = False
                self._save_atomic_sync()

            await asyncio.to_thread(_do)

    async def save(self) -> None:
        await asyncio.to_thread(self._save_atomic_sync)

    async def load(self) -> None:
        async with self._lock:
            def _do() -> None:
                self._index = None
                self._ids = set()
                self.needs_rebuild = False
                if not self._index_file.exists():
                    self.needs_rebuild = True
                    return
                index = faiss.read_index(str(self._index_file))
                if not isinstance(index, faiss.IndexIDMap):
                    self.needs_rebuild = True  # 旧 IndexFlat 格式
                    return
                self._index = index
                self._ids = set(
                    int(fid)
                    for fid in faiss.vector_to_array(index.id_map).tolist()
                )

            await asyncio.to_thread(_do)
