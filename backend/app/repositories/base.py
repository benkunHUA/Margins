"""仓储接口。

业务只依赖此处抽象；SQLAlchemy 实现与内存实现需满足同一套行为断言。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
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


class DocumentRepository(ABC):
    @abstractmethod
    async def create(self, doc: Document) -> Document: ...

    @abstractmethod
    async def get(self, doc_id: UUID) -> Document | None: ...

    @abstractmethod
    async def list(
        self,
        *,
        page: int,
        page_size: int,
        status: DocumentStatus | None = None,
        q: str | None = None,
    ) -> Page[Document]: ...

    @abstractmethod
    async def update(self, doc: Document) -> Document: ...

    @abstractmethod
    async def delete(self, doc_id: UUID) -> None: ...

    @abstractmethod
    async def list_all(self) -> list[Document]: ...


class ChunkRepository(ABC):
    @abstractmethod
    async def add_many(self, chunks: Sequence[Chunk]) -> None: ...

    @abstractmethod
    async def list_by_document(self, doc_id: UUID) -> list[Chunk]: ...

    @abstractmethod
    async def delete_by_document(self, doc_id: UUID) -> None: ...

    @abstractmethod
    async def list_all(self) -> list[Chunk]: ...

    @abstractmethod
    async def get_many(self, chunk_ids: Sequence[UUID]) -> list[Chunk]: ...


class SessionRepository(ABC):
    @abstractmethod
    async def create(self, session: Session) -> Session: ...

    @abstractmethod
    async def get(self, session_id: UUID) -> Session | None: ...

    @abstractmethod
    async def list(self, *, page: int, page_size: int) -> Page[Session]: ...

    @abstractmethod
    async def delete(self, session_id: UUID) -> None: ...

    @abstractmethod
    async def add_message(self, msg: Message) -> Message: ...

    @abstractmethod
    async def list_messages(self, session_id: UUID, *, limit: int) -> list[Message]: ...


class ParseJobRepository(ABC):
    @abstractmethod
    async def create(self, job: ParseJob) -> ParseJob: ...

    @abstractmethod
    async def update(self, job: ParseJob) -> ParseJob: ...

    @abstractmethod
    async def get(self, job_id: UUID) -> ParseJob | None: ...
