"""基于内存字典的仓储实现（骨架阶段默认使用，后续由 SQL 实现替换）。"""

from __future__ import annotations

import asyncio
from collections.abc import Sequence
from uuid import UUID

from app.domain.entities import (
    Chunk,
    Document,
    Message,
    Page,
    ParseJob,
    Session,
)
from app.domain.enums import DocumentStatus
from app.repositories.base import (
    ChunkRepository,
    DocumentRepository,
    ParseJobRepository,
    SessionRepository,
)


class InMemoryDocumentRepository(DocumentRepository):
    def __init__(self) -> None:
        self._items: dict[UUID, Document] = {}
        self._lock = asyncio.Lock()

    async def create(self, doc: Document) -> Document:
        async with self._lock:
            self._items[doc.id] = doc
        return doc

    async def get(self, doc_id: UUID) -> Document | None:
        return self._items.get(doc_id)

    async def list(
        self,
        *,
        page: int,
        page_size: int,
        status: DocumentStatus | None = None,
        q: str | None = None,
    ) -> Page[Document]:
        items = list(self._items.values())
        if status is not None:
            items = [d for d in items if d.status == status]
        if q:
            lowered = q.lower()
            items = [d for d in items if lowered in d.filename.lower()]
        items.sort(key=lambda d: d.created_at, reverse=True)
        total = len(items)
        start = (page - 1) * page_size
        return Page(
            items=items[start : start + page_size],
            total=total,
            page=page,
            page_size=page_size,
        )

    async def update(self, doc: Document) -> Document:
        async with self._lock:
            self._items[doc.id] = doc
        return doc

    async def delete(self, doc_id: UUID) -> None:
        async with self._lock:
            self._items.pop(doc_id, None)

    async def list_all(self) -> list[Document]:
        return list(self._items.values())


class InMemoryChunkRepository(ChunkRepository):
    def __init__(self) -> None:
        self._items: dict[UUID, Chunk] = {}

    async def add_many(self, chunks: Sequence[Chunk]) -> None:
        self._items.update({c.id: c for c in chunks})

    async def list_by_document(self, doc_id: UUID) -> list[Chunk]:
        return [c for c in self._items.values() if c.document_id == doc_id]

    async def delete_by_document(self, doc_id: UUID) -> None:
        for cid in [c.id for c in self._items.values() if c.document_id == doc_id]:
            self._items.pop(cid, None)

    async def list_all(self) -> list[Chunk]:
        return list(self._items.values())

    async def get_many(self, chunk_ids: Sequence[UUID]) -> list[Chunk]:
        return [self._items[cid] for cid in chunk_ids if cid in self._items]


class InMemorySessionRepository(SessionRepository):
    def __init__(self) -> None:
        self._sessions: dict[UUID, Session] = {}
        self._messages: dict[UUID, list[Message]] = {}

    async def create(self, session: Session) -> Session:
        self._sessions[session.id] = session
        self._messages.setdefault(session.id, [])
        return session

    async def get(self, session_id: UUID) -> Session | None:
        return self._sessions.get(session_id)

    async def list(self, *, page: int, page_size: int) -> Page[Session]:
        items = sorted(self._sessions.values(), key=lambda s: s.created_at, reverse=True)
        total = len(items)
        start = (page - 1) * page_size
        return Page(
            items=items[start : start + page_size],
            total=total,
            page=page,
            page_size=page_size,
        )

    async def delete(self, session_id: UUID) -> None:
        self._sessions.pop(session_id, None)
        self._messages.pop(session_id, None)

    async def add_message(self, msg: Message) -> Message:
        self._messages.setdefault(msg.session_id, []).append(msg)
        return msg

    async def list_messages(self, session_id: UUID, *, limit: int) -> list[Message]:
        return self._messages.get(session_id, [])[-limit:]

    async def update_title(self, session_id: UUID, title: str) -> Session:
        session = self._sessions[session_id]
        session.title = title
        return session


class InMemoryParseJobRepository(ParseJobRepository):
    def __init__(self) -> None:
        self._items: dict[UUID, ParseJob] = {}
        self._order: list[UUID] = []

    async def create(self, job: ParseJob) -> ParseJob:
        self._items[job.id] = job
        self._order.append(job.id)
        return job

    async def update(self, job: ParseJob) -> ParseJob:
        self._items[job.id] = job
        return job

    async def get(self, job_id: UUID) -> ParseJob | None:
        return self._items.get(job_id)

    async def get_by_document(self, doc_id: UUID) -> ParseJob | None:
        for job_id in reversed(self._order):
            job = self._items.get(job_id)
            if job is not None and job.document_id == doc_id:
                return job
        return None
