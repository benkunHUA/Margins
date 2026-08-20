"""会话与问答编排服务。"""

from collections.abc import AsyncIterator
from uuid import UUID

from app.core.exceptions import SessionNotFoundError
from app.domain.entities import Message, Page, Session
from app.domain.events import ErrorEvent, RagEvent
from app.repositories.base import SessionRepository
from app.services.rag.pipeline import RAGPipeline


class ChatService:
    def __init__(self, sessions: SessionRepository, rag: RAGPipeline) -> None:
        self._sessions = sessions
        self._rag = rag

    async def create_session(self) -> Session:
        return await self._sessions.create(Session())

    async def list_sessions(self, *, page: int, page_size: int) -> Page[Session]:
        return await self._sessions.list(page=page, page_size=page_size)

    async def get_session(self, session_id: UUID) -> Session:
        session = await self._sessions.get(session_id)
        if session is None:
            raise SessionNotFoundError(f"会话不存在: {session_id}")
        return session

    async def delete_session(self, session_id: UUID) -> None:
        await self.get_session(session_id)
        await self._sessions.delete(session_id)

    async def list_messages(self, session_id: UUID, *, limit: int) -> list[Message]:
        await self.get_session(session_id)
        return await self._sessions.list_messages(session_id, limit=limit)

    async def ask(self, session_id: UUID, question: str) -> AsyncIterator[RagEvent]:
        """M2 落地：落库 user 消息 → rag.run → 转发事件 → 落库 assistant 消息。"""
        await self.get_session(session_id)
        yield ErrorEvent(code="NOT_IMPLEMENTED", message="问答功能将在 M2 里程碑实现")
