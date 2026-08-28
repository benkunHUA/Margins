"""ChatService 测试（fake sessions 仓储 + fake rag）。"""

from uuid import uuid4

from app.core.constants import SESSION_TITLE_MAX_CHARS
from app.domain.entities import Citation, Message
from app.domain.enums import MessageRole
from app.domain.events import (
    CitationsEvent,
    DeltaEvent,
    DoneEvent,
    ErrorEvent,
    MetaEvent,
)
from app.repositories.memory.memory_repos import InMemorySessionRepository
from app.services.chat_service import ChatService


class FakeRag:
    def __init__(self) -> None:
        self.runs: list[tuple[str, list[Message]]] = []

    async def run(self, question, history):
        self.runs.append((question, list(history)))
        yield CitationsEvent(
            citations=[
                Citation(chunk_id=uuid4(), document_id=uuid4(), doc_title="a", snippet="s")
            ]
        )
        for token in ["答", "案"]:
            yield DeltaEvent(content=token)


async def test_ask_persists_messages_and_emits_events() -> None:
    sessions = InMemorySessionRepository()
    rag = FakeRag()
    service = ChatService(sessions, rag, history_limit=6)
    session = await service.create_session()

    events = [event async for event in service.ask(session.id, "违约金多少？")]

    assert isinstance(events[0], MetaEvent)
    assert any(isinstance(event, CitationsEvent) for event in events)
    assert any(isinstance(event, DeltaEvent) for event in events)
    assert isinstance(events[-1], DoneEvent)

    messages = await sessions.list_messages(session.id, limit=10)
    assert [m.role for m in messages] == [MessageRole.USER, MessageRole.ASSISTANT]
    assert messages[1].content == "答案"
    assert len(messages[1].citations) == 1
    assert (await sessions.get(session.id)).title == "违约金多少？"[:SESSION_TITLE_MAX_CHARS]
    assert rag.runs[0][0] == "违约金多少？"


async def test_ask_emits_error_without_persisting_assistant() -> None:
    class BoomRag(FakeRag):
        async def run(self, question, history):
            raise RuntimeError("boom")
            yield  # 使方法成为 async generator，异常在迭代时抛出

    sessions = InMemorySessionRepository()
    service = ChatService(sessions, BoomRag(), history_limit=6)
    session = await service.create_session()

    events = [event async for event in service.ask(session.id, "q")]
    assert isinstance(events[-1], ErrorEvent)
    messages = await sessions.list_messages(session.id, limit=10)
    assert [m.role for m in messages] == [MessageRole.USER]
