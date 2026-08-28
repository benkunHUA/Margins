"""SQL 仓储实现测试（临时 SQLite 文件库）。"""

from uuid import uuid4

import pytest

from app.domain.entities import Chunk, Citation, Document, Message, ParseJob, Session
from app.domain.enums import DocumentStatus, MessageRole, ParseJobStatus
from app.repositories.sql.chunks import ChunkSqlRepository
from app.repositories.sql.database import create_engine_and_sessionmaker, init_db
from app.repositories.sql.documents import DocumentSqlRepository
from app.repositories.sql.sessions import ParseJobSqlRepository, SessionSqlRepository


@pytest.fixture
async def repos(tmp_path):
    engine, session_factory = create_engine_and_sessionmaker(tmp_path)
    await init_db(engine)
    yield (
        DocumentSqlRepository(session_factory),
        ChunkSqlRepository(session_factory),
        ParseJobSqlRepository(session_factory),
        SessionSqlRepository(session_factory),
    )
    await engine.dispose()


def _doc(**overrides) -> Document:
    defaults = dict(
        filename="a.pdf",
        file_type="pdf",
        file_size=10,
        file_path=__file__,
    )
    return Document(**defaults, **overrides)


async def test_document_crud_and_filter(repos) -> None:
    documents, _, _, _ = repos
    d1 = await documents.create(_doc())
    await documents.create(_doc(status=DocumentStatus.READY))

    assert (await documents.get(d1.id)) is not None
    page = await documents.list(page=1, page_size=10, status=DocumentStatus.PENDING)
    assert [item.id for item in page.items] == [d1.id]

    page = await documents.list(page=1, page_size=10, q="a.pdf")
    assert page.total == 2
    assert page.page == 1

    d1.status = DocumentStatus.FAILED
    await documents.update(d1)
    assert (await documents.get(d1.id)).status == DocumentStatus.FAILED

    await documents.delete(d1.id)
    assert await documents.get(d1.id) is None
    assert len(await documents.list_all()) == 1


async def test_chunk_repository(repos) -> None:
    documents, chunks, _, _ = repos
    doc_id = uuid4()
    await documents.create(_doc(id=doc_id))
    c1 = Chunk(id=uuid4(), document_id=doc_id, chunk_index=0, content="a")
    c2 = Chunk(id=uuid4(), document_id=doc_id, chunk_index=1, content="b")
    await chunks.add_many([c1, c2])

    assert [c.id for c in await chunks.list_by_document(doc_id)] == [c1.id, c2.id]
    assert [c.id for c in await chunks.get_many([c1.id, c2.id])] == [c1.id, c2.id]

    await chunks.delete_by_document(doc_id)
    assert await chunks.list_by_document(doc_id) == []
    assert await chunks.list_all() == []


async def test_parse_job_repository_latest_by_document(repos) -> None:
    _, _, jobs, _ = repos
    doc_id = uuid4()
    await jobs.create(ParseJob(document_id=doc_id))
    j2 = await jobs.create(ParseJob(document_id=doc_id))

    latest = await jobs.get_by_document(doc_id)
    assert latest.id == j2.id

    j2.status = ParseJobStatus.RUNNING
    await jobs.update(j2)
    assert (await jobs.get(j2.id)).status == ParseJobStatus.RUNNING


async def test_session_repository(repos) -> None:
    _, _, _, sessions = repos
    session = await sessions.create(Session())
    assert (await sessions.get(session.id)) is not None
    await sessions.update_title(session.id, "第一个问题")
    assert (await sessions.get(session.id)).title == "第一个问题"

    await sessions.add_message(
        Message(session_id=session.id, role=MessageRole.USER, content="hi")
    )
    await sessions.add_message(
        Message(session_id=session.id, role=MessageRole.ASSISTANT, content="hello")
    )
    msgs = await sessions.list_messages(session.id, limit=10)
    assert len(msgs) == 2
    assert msgs[0].content == "hi"

    await sessions.delete(session.id)
    assert await sessions.get(session.id) is None
    assert await sessions.list_messages(session.id, limit=10) == []  # 级联删除消息


async def test_session_message_citations_roundtrip(repos) -> None:
    _, _, _, sessions = repos
    session = await sessions.create(Session())
    citation = Citation(chunk_id=uuid4(), document_id=uuid4(), doc_title="a", snippet="s")
    await sessions.add_message(
        Message(
            session_id=session.id,
            role=MessageRole.ASSISTANT,
            content="x",
            citations=[citation],
        )
    )

    messages = await sessions.list_messages(session.id, limit=10)
    assert len(messages[0].citations) == 1
    assert messages[0].citations[0].chunk_id == citation.chunk_id
