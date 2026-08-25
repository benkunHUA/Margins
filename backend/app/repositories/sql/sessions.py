"""Session / Message / ParseJob 的 SQL 实现（M2 补 Session、Message）。"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.domain.entities import ParseJob
from app.domain.enums import ParseJobStatus
from app.repositories.base import ParseJobRepository
from app.repositories.sql.models import ParseJobRow


def _row(job: ParseJob) -> ParseJobRow:
    return ParseJobRow(
        id=str(job.id),
        document_id=str(job.document_id),
        status=job.status.value,
        attempt=job.attempt,
        last_error=job.last_error,
        queued_at=job.queued_at,
        started_at=job.started_at,
        finished_at=job.finished_at,
    )


def _entity(row: ParseJobRow) -> ParseJob:
    return ParseJob(
        id=UUID(row.id),
        document_id=UUID(row.document_id),
        status=ParseJobStatus(row.status),
        attempt=row.attempt,
        last_error=row.last_error,
        queued_at=row.queued_at,
        started_at=row.started_at,
        finished_at=row.finished_at,
    )


class ParseJobSqlRepository(ParseJobRepository):
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._sf = session_factory

    async def create(self, job: ParseJob) -> ParseJob:
        async with self._sf() as session:
            session.add(_row(job))
            await session.commit()
        return job

    async def update(self, job: ParseJob) -> ParseJob:
        async with self._sf() as session:
            row = await session.get(ParseJobRow, str(job.id))
            if row is None:
                session.add(_row(job))
            else:
                row.status = job.status.value
                row.attempt = job.attempt
                row.last_error = job.last_error
                row.started_at = job.started_at
                row.finished_at = job.finished_at
            await session.commit()
        return job

    async def get(self, job_id: UUID) -> ParseJob | None:
        async with self._sf() as session:
            row = await session.get(ParseJobRow, str(job_id))
            return _entity(row) if row else None

    async def get_by_document(self, doc_id: UUID) -> ParseJob | None:
        async with self._sf() as session:
            row = (
                await session.execute(
                    select(ParseJobRow)
                    .where(ParseJobRow.document_id == str(doc_id))
                    .order_by(ParseJobRow.queued_at.desc())
                    .limit(1)
                )
            ).scalar_one_or_none()
            return _entity(row) if row else None
