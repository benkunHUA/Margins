"""查询链路日志接口。"""

from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.api.dependencies import get_query_log_service
from app.api.schemas.logs import QueryLogDetailOut, QueryLogSummaryOut
from app.domain.entities import Page, QueryLog
from app.services.query_log_service import QueryLogService

router = APIRouter(prefix="/api/logs", tags=["logs"])


def _summary(log: QueryLog) -> QueryLogSummaryOut:
    excerpt = (log.answer or "").strip()
    return QueryLogSummaryOut(
        id=log.id,
        session_id=log.session_id,
        session_title=log.session_title,
        question=log.question,
        status=log.status,
        error=log.error,
        total_ms=log.total_ms,
        citation_count=len(log.citations),
        answer_excerpt=excerpt[:200] if excerpt else None,
        created_at=log.created_at,
    )


@router.get("", response_model=Page[QueryLogSummaryOut])
async def list_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    q: str | None = Query(None),
    session_id: UUID | None = Query(None),
    status: str | None = Query(None, pattern="^(success|failed)$"),
    service: QueryLogService = Depends(get_query_log_service),
) -> Page[QueryLogSummaryOut]:
    result = await service.list(
        page=page,
        page_size=page_size,
        q=q,
        session_id=session_id,
        status=status,
    )
    return Page(
        items=[_summary(log) for log in result.items],
        total=result.total,
        page=result.page,
        page_size=result.page_size,
    )


@router.get("/{log_id}", response_model=QueryLogDetailOut)
async def get_log(
    log_id: UUID,
    service: QueryLogService = Depends(get_query_log_service),
) -> QueryLogDetailOut:
    return QueryLogDetailOut.model_validate(await service.get(log_id))
