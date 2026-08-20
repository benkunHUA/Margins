"""会话与问答接口（含 SSE 流式）。"""

from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response
from fastapi.responses import StreamingResponse

from app.api.dependencies import get_chat_service
from app.api.schemas.chat import format_sse
from app.api.schemas.sessions import ChatRequest, MessageOut, SessionDetail, SessionOut
from app.domain.entities import Page
from app.services.chat_service import ChatService

router = APIRouter(prefix="/api/sessions", tags=["sessions"])


@router.post("", status_code=201, response_model=SessionOut)
async def create_session(
    service: ChatService = Depends(get_chat_service),
) -> SessionOut:
    session = await service.create_session()
    return SessionOut.model_validate(session)


@router.get("", response_model=Page[SessionOut])
async def list_sessions(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    service: ChatService = Depends(get_chat_service),
) -> Page[SessionOut]:
    result = await service.list_sessions(page=page, page_size=page_size)
    return Page(
        items=[SessionOut.model_validate(s) for s in result.items],
        total=result.total,
        page=result.page,
        page_size=result.page_size,
    )


@router.get("/{session_id}", response_model=SessionDetail)
async def get_session(
    session_id: UUID,
    service: ChatService = Depends(get_chat_service),
) -> SessionDetail:
    session = await service.get_session(session_id)
    messages = await service.list_messages(session_id, limit=100)
    return SessionDetail(
        session=SessionOut.model_validate(session),
        messages=[MessageOut.model_validate(m) for m in messages],
    )


@router.delete("/{session_id}", status_code=204)
async def delete_session(
    session_id: UUID,
    service: ChatService = Depends(get_chat_service),
) -> Response:
    await service.delete_session(session_id)
    return Response(status_code=204)


@router.post("/{session_id}/messages")
async def ask(
    session_id: UUID,
    body: ChatRequest,
    service: ChatService = Depends(get_chat_service),
) -> StreamingResponse:
    async def event_stream():
        async for event in service.ask(session_id, body.question):
            yield format_sse(event)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
