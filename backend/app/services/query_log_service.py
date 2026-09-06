"""查询链路日志服务。"""

from uuid import UUID

from app.core.exceptions import QueryLogNotFoundError
from app.domain.entities import Page, QueryLog
from app.repositories.base import QueryLogRepository


class QueryLogService:
    def __init__(self, logs: QueryLogRepository) -> None:
        self._logs = logs

    async def list(
        self,
        *,
        page: int,
        page_size: int,
        q: str | None = None,
        session_id: UUID | None = None,
        status: str | None = None,
    ) -> Page[QueryLog]:
        return await self._logs.list(
            page=page,
            page_size=page_size,
            q=q,
            session_id=session_id,
            status=status,
        )

    async def get(self, log_id: UUID) -> QueryLog:
        log = await self._logs.get(log_id)
        if log is None:
            raise QueryLogNotFoundError(f"查询日志不存在: {log_id}")
        return log
