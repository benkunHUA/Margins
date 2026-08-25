"""DocumentRepository 的 SQL 实现。"""

from __future__ import annotations

import json
from pathlib import Path
from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.domain.entities import Document, Page
from app.domain.enums import DocumentStatus
from app.repositories.base import DocumentRepository
from app.repositories.sql.models import DocumentRow


def _row(doc: Document) -> DocumentRow:
    return DocumentRow(
        id=str(doc.id),
        filename=doc.filename,
        file_type=doc.file_type,
        file_size=doc.file_size,
        file_path=str(doc.file_path),
        markdown_path=str(doc.markdown_path) if doc.markdown_path else None,
        status=doc.status.value,
        parse_error=doc.parse_error,
        extra=json.dumps(doc.extra, ensure_ascii=False),
        created_at=doc.created_at,
        updated_at=doc.updated_at,
    )


def _entity(row: DocumentRow) -> Document:
    return Document(
        id=UUID(row.id),
        filename=row.filename,
        file_type=row.file_type,
        file_size=row.file_size,
        file_path=Path(row.file_path),
        markdown_path=Path(row.markdown_path) if row.markdown_path else None,
        status=DocumentStatus(row.status),
        parse_error=row.parse_error,
        extra=json.loads(row.extra),
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _apply(row: DocumentRow, doc: Document) -> None:
    row.filename = doc.filename
    row.file_type = doc.file_type
    row.file_size = doc.file_size
    row.file_path = str(doc.file_path)
    row.markdown_path = str(doc.markdown_path) if doc.markdown_path else None
    row.status = doc.status.value
    row.parse_error = doc.parse_error
    row.extra = json.dumps(doc.extra, ensure_ascii=False)
    row.updated_at = doc.updated_at


class DocumentSqlRepository(DocumentRepository):
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._sf = session_factory

    async def create(self, doc: Document) -> Document:
        async with self._sf() as session:
            session.add(_row(doc))
            await session.commit()
        return doc

    async def get(self, doc_id: UUID) -> Document | None:
        async with self._sf() as session:
            row = await session.get(DocumentRow, str(doc_id))
            return _entity(row) if row else None

    async def list(
        self,
        *,
        page: int,
        page_size: int,
        status: DocumentStatus | None = None,
        q: str | None = None,
    ) -> Page[Document]:
        async with self._sf() as session:
            stmt = select(DocumentRow)
            count_stmt = select(func.count()).select_from(DocumentRow)
            if status is not None:
                stmt = stmt.where(DocumentRow.status == status.value)
                count_stmt = count_stmt.where(DocumentRow.status == status.value)
            if q:
                pattern = f"%{q}%"
                stmt = stmt.where(DocumentRow.filename.like(pattern))
                count_stmt = count_stmt.where(DocumentRow.filename.like(pattern))
            total = (await session.execute(count_stmt)).scalar_one()
            rows = (
                await session.execute(
                    stmt.order_by(DocumentRow.created_at.desc())
                    .offset((page - 1) * page_size)
                    .limit(page_size)
                )
            ).scalars().all()
            return Page(
                items=[_entity(row) for row in rows],
                total=total,
                page=page,
                page_size=page_size,
            )

    async def update(self, doc: Document) -> Document:
        async with self._sf() as session:
            row = await session.get(DocumentRow, str(doc.id))
            if row is None:
                session.add(_row(doc))
            else:
                _apply(row, doc)
            await session.commit()
        return doc

    async def delete(self, doc_id: UUID) -> None:
        async with self._sf() as session:
            await session.execute(delete(DocumentRow).where(DocumentRow.id == str(doc_id)))
            await session.commit()

    async def list_all(self) -> list[Document]:
        async with self._sf() as session:
            rows = (await session.execute(select(DocumentRow))).scalars().all()
            return [_entity(row) for row in rows]
