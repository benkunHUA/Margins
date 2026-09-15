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
    EvalDataset,
    EvalRun,
    EvalRunItem,
    Message,
    Page,
    ParseJob,
    QueryLog,
    Session,
)
from app.domain.enums import DocumentStatus, EvalItemStatus


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

    async def get_by_faiss_ids(self, faiss_ids: Sequence[int]) -> list[Chunk]:
        raise NotImplementedError

    async def allocate_missing_ids(self) -> int:
        return 0


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

    @abstractmethod
    async def update_title(self, session_id: UUID, title: str) -> Session: ...


class ParseJobRepository(ABC):
    @abstractmethod
    async def create(self, job: ParseJob) -> ParseJob: ...

    @abstractmethod
    async def update(self, job: ParseJob) -> ParseJob: ...

    @abstractmethod
    async def get(self, job_id: UUID) -> ParseJob | None: ...

    @abstractmethod
    async def get_by_document(self, doc_id: UUID) -> ParseJob | None: ...


class QueryLogRepository(ABC):
    @abstractmethod
    async def create(self, log: QueryLog) -> QueryLog: ...

    @abstractmethod
    async def get(self, log_id: UUID) -> QueryLog | None: ...

    @abstractmethod
    async def list(
        self,
        *,
        page: int,
        page_size: int,
        q: str | None = None,
        session_id: UUID | None = None,
        status: str | None = None,
    ) -> Page[QueryLog]: ...


class EvalDatasetRepository(ABC):
    @abstractmethod
    async def create(self, dataset: EvalDataset) -> EvalDataset: ...

    @abstractmethod
    async def get(self, dataset_id: UUID) -> EvalDataset | None: ...

    @abstractmethod
    async def get_by_name(self, name: str) -> EvalDataset | None: ...

    @abstractmethod
    async def list_all(self) -> list[EvalDataset]: ...

    @abstractmethod
    async def delete(self, dataset_id: UUID) -> None: ...


class EvalRunRepository(ABC):
    @abstractmethod
    async def create(self, run: EvalRun) -> EvalRun: ...

    @abstractmethod
    async def update(self, run: EvalRun) -> EvalRun: ...

    @abstractmethod
    async def get(self, run_id: UUID) -> EvalRun | None: ...

    @abstractmethod
    async def list(self, *, page: int, page_size: int) -> Page[EvalRun]: ...

    @abstractmethod
    async def get_running(self) -> EvalRun | None: ...

    @abstractmethod
    async def mark_active_failed(self, error: str) -> int: ...


class EvalRunItemRepository(ABC):
    @abstractmethod
    async def add_many(self, items: Sequence[EvalRunItem]) -> None: ...

    @abstractmethod
    async def list(
        self,
        *,
        run_id: UUID,
        page: int,
        page_size: int,
        config_index: int | None = None,
        item_status: EvalItemStatus | None = None,
        relocated: bool | None = None,
    ) -> Page[EvalRunItem]: ...
