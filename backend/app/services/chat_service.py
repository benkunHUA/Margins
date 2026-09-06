"""会话与问答编排服务。"""

import logging
import time
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
from app.repositories.base import QueryLogRepository, SessionRepository
from app.services.rag.pipeline import RAGPipeline
from app.services.rag.trace import Trace

logger = logging.getLogger(__name__)


class ChatService:
    def __init__(
        self,
        sessions: SessionRepository,
        rag: RAGPipeline,
        history_limit: int = 6,
        logs: QueryLogRepository | None = None,
    ) -> None:
        self._sessions = sessions
        self._rag = rag
        self._history_limit = history_limit
        self._logs = logs

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

        trace: Trace | None = None
        if self._logs is not None:
            trace = Trace(
                session_id=session_id,
                session_title=session.title,
                question=question,
            )
        started = time.perf_counter()
        status = "success"
        error: str | None = None

        parts: list[str] = []
        citations: list[Citation] = []
        try:
            if trace is not None:
                rag_iter = self._rag.run(question, history, trace=trace)
            else:
                rag_iter = self._rag.run(question, history)
            async for event in rag_iter:
                if isinstance(event, CitationsEvent):
                    citations = event.citations
                    yield event
                elif isinstance(event, DeltaEvent):
                    parts.append(event.content)
                    yield event
                elif isinstance(event, ErrorEvent):
                    status = "failed"
                    error = event.message
                    yield event
                    return
        except Exception as exc:
            status = "failed"
            error = str(exc)
            yield ErrorEvent(code="CHAT_ERROR", message=str(exc))
            return
        finally:
            if self._logs is not None and trace is not None:
                await self._persist_log(
                    trace,
                    session_id=session_id,
                    status=status,
                    error=error,
                    answer="".join(parts) if status == "success" else None,
                    citations=citations,
                    started=started,
                )

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

    async def _persist_log(
        self,
        trace: Trace,
        *,
        session_id: UUID,
        status: str,
        error: str | None,
        answer: str | None,
        citations: list[Citation],
        started: float,
    ) -> None:
        try:
            assert self._logs is not None
            session = await self.get_session(session_id)
            log = trace.build(
                status=status,
                error=error,
                answer=answer,
                citations=citations,
                total_ms=round((time.perf_counter() - started) * 1000, 1),
                created_at=datetime.now(UTC),
            )
            log.session_title = session.title
            await self._logs.create(log)
        except Exception:
            logger.warning("查询链路日志落库失败（不影响问答）", exc_info=True)
