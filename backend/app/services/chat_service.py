"""会话与问答编排服务。"""

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from uuid import UUID, uuid4

from app.core.constants import SESSION_TITLE_MAX_CHARS
from app.core.exceptions import SessionNotFoundError
from app.domain.entities import Citation, Message, Page, Session
from app.domain.enums import MessageRole
from app.domain.events import (
    CitationsEvent,
    DeltaEvent,
    DoneEvent,
    ErrorEvent,
    MetaEvent,
    RagEvent,
)
from app.repositories.base import SessionRepository
from app.services.rag.pipeline import RAGPipeline


class ChatService:
    def __init__(
        self,
        sessions: SessionRepository,
        rag: RAGPipeline,
        history_limit: int = 6,
    ) -> None:
        self._sessions = sessions
        self._rag = rag
        self._history_limit = history_limit

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
        session = await self.get_session(session_id)
        await self._sessions.add_message(
            Message(session_id=session_id, role=MessageRole.USER, content=question)
        )
        all_messages = await self._sessions.list_messages(
            session_id, limit=self._history_limit + 1
        )
        history = all_messages[:-1]  # 去掉刚写入的当前问题

        if session.title == "新会话":
            await self._sessions.update_title(session_id, question[:SESSION_TITLE_MAX_CHARS])

        assistant_id = uuid4()
        yield MetaEvent(session_id=str(session_id), message_id=str(assistant_id))

        parts: list[str] = []
        citations: list[Citation] = []
        try:
            async for event in self._rag.run(question, history):
                if isinstance(event, CitationsEvent):
                    citations = event.citations
                    yield event
                elif isinstance(event, DeltaEvent):
                    parts.append(event.content)
                    yield event
                elif isinstance(event, ErrorEvent):
                    yield event
                    return
        except Exception as exc:
            yield ErrorEvent(code="CHAT_ERROR", message=str(exc))
            return

        await self._sessions.add_message(
            Message(
                session_id=session_id,
                role=MessageRole.ASSISTANT,
                content="".join(parts),
                citations=citations,
                created_at=datetime.now(UTC),
            )
        )
        yield DoneEvent(message_id=str(assistant_id))
