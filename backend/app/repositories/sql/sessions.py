"""Session / Message / ParseJob 的 SQL 实现。"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.exceptions import SessionNotFoundError
from app.domain.entities import Citation, Message, Page, ParseJob, Session
from app.domain.enums import MessageRole, ParseJobStatus
from app.repositories.base import ParseJobRepository, SessionRepository
from app.repositories.sql.models import MessageRow, ParseJobRow, SessionRow


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


def _session_row(session: Session) -> SessionRow:
    return SessionRow(
        id=str(session.id),
        title=session.title,
        created_at=session.created_at,
        updated_at=session.updated_at,
    )


def _session_entity(row: SessionRow) -> Session:
    return Session(
        id=UUID(row.id),
        title=row.title,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _message_row(msg: Message) -> MessageRow:
    return MessageRow(
        id=str(msg.id),
        session_id=str(msg.session_id),
        role=msg.role.value,
        content=msg.content,
        citations=json.dumps([c.model_dump() for c in msg.citations], ensure_ascii=False),
        created_at=msg.created_at,
    )


def _message_entity(row: MessageRow) -> Message:
    return Message(
        id=UUID(row.id),
        session_id=UUID(row.session_id),
        role=MessageRole(row.role),
        content=row.content,
        citations=[Citation.model_validate(item) for item in json.loads(row.citations)],
        created_at=row.created_at,
    )


class SessionSqlRepository(SessionRepository):
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._sf = session_factory

    async def create(self, session: Session) -> Session:
        async with self._sf() as s:
            s.add(_session_row(session))
            await s.commit()
        return session

    async def get(self, session_id: UUID) -> Session | None:
        async with self._sf() as s:
            row = await s.get(SessionRow, str(session_id))
            return _session_entity(row) if row else None

    async def list(self, *, page: int, page_size: int) -> Page[Session]:
        async with self._sf() as s:
            total = (await s.execute(select(func.count()).select_from(SessionRow))).scalar_one()
            rows = (
                await s.execute(
                    select(SessionRow)
                    .order_by(SessionRow.created_at.desc())
                    .offset((page - 1) * page_size)
                    .limit(page_size)
                )
            ).scalars().all()
            return Page(
                items=[_session_entity(r) for r in rows],
                total=total,
                page=page,
                page_size=page_size,
            )

    async def update_title(self, session_id: UUID, title: str) -> Session:
        async with self._sf() as s:
            row = await s.get(SessionRow, str(session_id))
            if row is None:
                raise SessionNotFoundError(f"会话不存在: {session_id}")
            row.title = title
            row.updated_at = datetime.now(UTC)
            await s.commit()
            return _session_entity(row)

    async def delete(self, session_id: UUID) -> None:
        async with self._sf() as s:
            await s.execute(delete(SessionRow).where(SessionRow.id == str(session_id)))
            await s.commit()

    async def add_message(self, msg: Message) -> Message:
        async with self._sf() as s:
            s.add(_message_row(msg))
            await s.commit()
        return msg

    async def list_messages(self, session_id: UUID, *, limit: int) -> list[Message]:
        async with self._sf() as s:
            rows = (
                await s.execute(
                    select(MessageRow)
                    .where(MessageRow.session_id == str(session_id))
                    .order_by(MessageRow.created_at)
                    .limit(limit)
                )
            ).scalars().all()
            return [_message_entity(r) for r in rows]
