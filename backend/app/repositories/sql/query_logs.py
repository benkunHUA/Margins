"""QueryLogRepository 的 SQL 实现。"""

from __future__ import annotations

import json
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.domain.entities import Citation, Page, QueryLog, QueryLogStep
from app.repositories.base import QueryLogRepository
from app.repositories.sql.models import QueryLogRow


def _row(log: QueryLog) -> QueryLogRow:
    return QueryLogRow(
        id=str(log.id),
        session_id=str(log.session_id),
        session_title=log.session_title,
        question=log.question,
        status=log.status,
        error=log.error,
        total_ms=int(round(log.total_ms)),
        answer=log.answer,
        steps_json=json.dumps(
            [step.model_dump(mode="json") for step in log.steps],
            ensure_ascii=False,
        ),
        citations_json=json.dumps(
            [citation.model_dump(mode="json") for citation in log.citations],
            ensure_ascii=False,
        ),
        created_at=log.created_at,
    )


def _entity(row: QueryLogRow) -> QueryLog:
    return QueryLog(
        id=UUID(row.id),
        session_id=UUID(row.session_id),
        session_title=row.session_title,
        question=row.question,
        status=row.status,
        error=row.error,
        total_ms=float(row.total_ms),
        answer=row.answer,
        steps=[QueryLogStep.model_validate(item) for item in json.loads(row.steps_json)],
        citations=[Citation.model_validate(item) for item in json.loads(row.citations_json)],
        created_at=row.created_at,
    )


class QueryLogSqlRepository(QueryLogRepository):
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._sf = session_factory

    async def create(self, log: QueryLog) -> QueryLog:
        async with self._sf() as session:
            session.add(_row(log))
            await session.commit()
        return log

    async def get(self, log_id: UUID) -> QueryLog | None:
        async with self._sf() as session:
            row = await session.get(QueryLogRow, str(log_id))
            return _entity(row) if row else None

    async def list(
        self,
        *,
        page: int,
        page_size: int,
        q: str | None = None,
        session_id: UUID | None = None,
        status: str | None = None,
    ) -> Page[QueryLog]:
        async with self._sf() as session:
            stmt = select(QueryLogRow)
            count_stmt = select(func.count()).select_from(QueryLogRow)
            if q:
                pattern = f"%{q}%"
                cond = or_(QueryLogRow.question.like(pattern), QueryLogRow.answer.like(pattern))
                stmt = stmt.where(cond)
                count_stmt = count_stmt.where(cond)
            if session_id is not None:
                stmt = stmt.where(QueryLogRow.session_id == str(session_id))
                count_stmt = count_stmt.where(QueryLogRow.session_id == str(session_id))
            if status is not None:
                stmt = stmt.where(QueryLogRow.status == status)
                count_stmt = count_stmt.where(QueryLogRow.status == status)
            total = (await session.execute(count_stmt)).scalar_one()
            rows = (
                await session.execute(
                    stmt.order_by(QueryLogRow.created_at.desc())
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
