"""ChunkRepository 的 SQL 实现。"""

from __future__ import annotations

import json
from collections.abc import Sequence
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.domain.entities import Chunk
from app.repositories.base import ChunkRepository
from app.repositories.sql.models import ChunkRow

_ALLOCATE = text(
    "UPDATE faiss_seq SET next_id = next_id + :n "
    "WHERE id = 1 RETURNING next_id - :n AS start"
)
_ENSURE_SEQ = text(
    "INSERT INTO faiss_seq (id, next_id) VALUES (1, 0) "
    "ON CONFLICT(id) DO NOTHING"
)


def _row(chunk: Chunk) -> ChunkRow:
    return ChunkRow(
        id=str(chunk.id),
        document_id=str(chunk.document_id),
        chunk_index=chunk.chunk_index,
        content=chunk.content,
        faiss_id=chunk.faiss_id,
        heading_path=chunk.heading_path,
        page=chunk.page,
        token_count=chunk.token_count,
        metadata_json=json.dumps(chunk.metadata, ensure_ascii=False),
        created_at=datetime.now(UTC),
    )


def _entity(row: ChunkRow) -> Chunk:
    return Chunk(
        id=UUID(row.id),
        document_id=UUID(row.document_id),
        chunk_index=row.chunk_index,
        content=row.content,
        faiss_id=row.faiss_id,
        heading_path=row.heading_path,
        page=row.page,
        token_count=row.token_count,
        metadata=json.loads(row.metadata_json),
    )


class ChunkSqlRepository(ChunkRepository):
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._sf = session_factory

    async def add_many(self, chunks: Sequence[Chunk]) -> None:
        async with self._sf() as session:
            pending = [chunk for chunk in chunks if chunk.faiss_id is None]
            if pending:
                await session.execute(_ENSURE_SEQ)
                start = (
                    await session.execute(_ALLOCATE, {"n": len(pending)})
                ).scalar_one()
                for offset, chunk in enumerate(pending):
                    chunk.faiss_id = start + offset
            session.add_all([_row(chunk) for chunk in chunks])
            await session.commit()

    async def list_by_document(self, doc_id: UUID) -> list[Chunk]:
        async with self._sf() as session:
            rows = (
                await session.execute(
                    select(ChunkRow)
                    .where(ChunkRow.document_id == str(doc_id))
                    .order_by(ChunkRow.chunk_index)
                )
            ).scalars().all()
            return [_entity(row) for row in rows]

    async def delete_by_document(self, doc_id: UUID) -> None:
        async with self._sf() as session:
            await session.execute(delete(ChunkRow).where(ChunkRow.document_id == str(doc_id)))
            await session.commit()

    async def list_all(self) -> list[Chunk]:
        async with self._sf() as session:
            rows = (await session.execute(select(ChunkRow))).scalars().all()
            return [_entity(row) for row in rows]

    async def get_many(self, chunk_ids: Sequence[UUID]) -> list[Chunk]:
        async with self._sf() as session:
            rows = (
                await session.execute(
                    select(ChunkRow)
                    .where(ChunkRow.id.in_([str(cid) for cid in chunk_ids]))
                    .order_by(ChunkRow.chunk_index)
                )
            ).scalars().all()
            return [_entity(row) for row in rows]

    async def get_by_faiss_ids(self, faiss_ids: Sequence[int]) -> list[Chunk]:
        if not faiss_ids:
            return []
        async with self._sf() as session:
            rows = (
                await session.execute(
                    select(ChunkRow)
                    .where(ChunkRow.faiss_id.in_(list(faiss_ids)))
                    .order_by(ChunkRow.chunk_index)
                )
            ).scalars().all()
            return [_entity(row) for row in rows]

    async def allocate_missing_ids(self) -> int:
        async with self._sf() as session:
            rows = (
                await session.execute(
                    select(ChunkRow)
                    .where(ChunkRow.faiss_id.is_(None))
                    .order_by(ChunkRow.id)
                )
            ).scalars().all()
            if not rows:
                return 0
            await session.execute(_ENSURE_SEQ)
            start = (
                await session.execute(_ALLOCATE, {"n": len(rows)})
            ).scalar_one()
            for offset, row in enumerate(rows):
                row.faiss_id = start + offset
            await session.commit()
            return len(rows)
