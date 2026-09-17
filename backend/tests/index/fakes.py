"""内存索引后端：端口契约的内存实现，供上层单测注入。"""

from collections.abc import Sequence
from uuid import UUID

from app.domain.entities import Chunk
from app.index.ports import (
    DenseIndexPort,
    IndexBackendPort,
    IndexChangeSet,
    IndexRecord,
    RetrievalScope,
    SparseIndexPort,
)
from app.index.values import ScoredChunk


def _cosine(left: Sequence[float], right: Sequence[float]) -> float:
    left_norm = sum(value * value for value in left) ** 0.5
    right_norm = sum(value * value for value in right) ** 0.5
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return sum(a * b for a, b in zip(left, right, strict=False)) / (left_norm * right_norm)


def _in_scope(record: IndexRecord, scope: RetrievalScope | None) -> bool:
    if scope is None or scope.is_global:
        return True
    return record.document_id in scope.document_ids


def _to_chunk(record: IndexRecord) -> Chunk:
    return Chunk(
        id=record.chunk_id,
        document_id=record.document_id,
        chunk_index=record.chunk_index,
        content=record.content,
        heading_path=record.heading_path,
        page=record.page,
        token_count=record.token_count,
        metadata=record.metadata,
    )


class _MemoryDense(DenseIndexPort):
    def __init__(self, records: dict[UUID, IndexRecord]) -> None:
        self.records = records

    async def upsert(self, records: Sequence[IndexRecord]) -> None:
        return None

    async def delete(self, chunk_ids: Sequence[UUID]) -> None:
        return None

    async def delete_by_document(self, document_id: UUID) -> None:
        return None

    async def search(
        self,
        embedding: list[float],
        k: int,
        scope: RetrievalScope | None = None,
    ) -> list[ScoredChunk]:
        items = [
            ScoredChunk(chunk=_to_chunk(record), score=_cosine(embedding, record.embedding))
            for record in self.records.values()
            if _in_scope(record, scope)
        ]
        items.sort(key=lambda item: item.score, reverse=True)
        return items[:k]


class _MemorySparse(SparseIndexPort):
    def __init__(self, records: dict[UUID, IndexRecord]) -> None:
        self.records = records

    async def upsert(self, records: Sequence[IndexRecord]) -> None:
        return None

    async def delete(self, chunk_ids: Sequence[UUID]) -> None:
        return None

    async def delete_by_document(self, document_id: UUID) -> None:
        return None

    async def search(
        self,
        query: str,
        k: int,
        scope: RetrievalScope | None = None,
    ) -> list[ScoredChunk]:
        tokens = [token for token in query.split() if token]
        items: list[ScoredChunk] = []
        for record in self.records.values():
            if not _in_scope(record, scope):
                continue
            score = sum(1 for token in tokens if token in record.content)
            if score:
                items.append(ScoredChunk(chunk=_to_chunk(record), score=float(score)))
        items.sort(key=lambda item: item.score, reverse=True)
        return items[:k]


class InMemoryIndexBackend(IndexBackendPort):
    """内存实现：语义与 SQLite 后端一致（先删后写、scope 过滤）。"""

    def __init__(self) -> None:
        self.records: dict[UUID, IndexRecord] = {}
        self.dense = _MemoryDense(self.records)
        self.sparse = _MemorySparse(self.records)

    async def initialize(self) -> None:
        return None

    async def close(self) -> None:
        return None

    async def stats(self) -> dict:
        documents = {record.document_id for record in self.records.values()}
        return {
            "chunks": len(self.records),
            "fts": len(self.records),
            "vectors": len(self.records),
            "documents": len(documents),
        }

    async def apply(self, change: IndexChangeSet) -> None:
        for chunk_id in change.delete_chunk_ids:
            self.records.pop(chunk_id, None)
        if change.delete_documents:
            doomed = set(change.delete_documents)
            for chunk_id in [
                key
                for key, record in self.records.items()
                if record.document_id in doomed
            ]:
                self.records.pop(chunk_id, None)
        for record in change.upserts:
            self.records[record.chunk_id] = record
