"""ChatService 日志落库测试（成功/失败/落库异常不打断回答）。"""

from uuid import uuid4

from app.domain.entities import Citation, QueryLog
from app.domain.events import CitationsEvent, DeltaEvent, DoneEvent, ErrorEvent
from app.repositories.memory.memory_repos import (
    InMemoryQueryLogRepository,
    InMemorySessionRepository,
)
from app.services.chat_service import ChatService


class FakeRag:
    async def run(self, question, history, *, trace=None):
        if trace is not None:
            trace.record(
                stage="rewrite",
                label="查询改写",
                duration_ms=10,
                summary="无需改写",
                data={"queries": [question]},
            )
        yield CitationsEvent(
            citations=[
                Citation(chunk_id=uuid4(), document_id=uuid4(), doc_title="a", snippet="s")
            ]
        )
        for token in ["答", "案"]:
            yield DeltaEvent(content=token)


class BoomRag(FakeRag):
    async def run(self, question, history, *, trace=None):
        raise RuntimeError("llm boom")
        yield  # pragma: no cover - 保持 async generator 语义


class RaisingLogRepo(InMemoryQueryLogRepository):
    async def create(self, log: QueryLog) -> QueryLog:
        raise RuntimeError("db down")


async def _events(service, session_id):
    return [event async for event in service.ask(session_id, "进展？")]


async def test_ask_persists_success_log() -> None:
    sessions = InMemorySessionRepository()
    logs = InMemoryQueryLogRepository()
    service = ChatService(sessions, FakeRag(), history_limit=6, logs=logs)
    session = await service.create_session()

    events = await _events(service, session.id)

    assert isinstance(events[-1], DoneEvent)
    stored = await logs.list(page=1, page_size=10)
    assert stored.total == 1
    log = stored.items[0]
    assert log.session_id == session.id
    assert log.session_title == "进展？"
    assert log.question == "进展？"
    assert log.status == "success"
    assert log.answer == "答案"
    assert len(log.citations) == 1
    assert [step.stage for step in log.steps] == ["rewrite"]
    assert log.total_ms >= 0


async def test_ask_persists_failed_log_with_error() -> None:
    sessions = InMemorySessionRepository()
    logs = InMemoryQueryLogRepository()
    service = ChatService(sessions, BoomRag(), history_limit=6, logs=logs)
    session = await service.create_session()

    events = await _events(service, session.id)

    assert isinstance(events[-1], ErrorEvent)
    stored = await logs.list(page=1, page_size=10)
    assert stored.total == 1
    assert stored.items[0].status == "failed"
    assert "llm boom" in (stored.items[0].error or "")
    assert stored.items[0].answer is None


async def test_log_write_failure_does_not_break_answer() -> None:
    sessions = InMemorySessionRepository()
    logs = RaisingLogRepo()
    service = ChatService(sessions, FakeRag(), history_limit=6, logs=logs)
    session = await service.create_session()

    events = await _events(service, session.id)

    assert isinstance(events[-1], DoneEvent)
    messages = await sessions.list_messages(session.id, limit=10)
    assert messages[-1].content == "答案"
