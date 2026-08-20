"""文档生命周期服务。"""

from collections.abc import Sequence
from uuid import UUID

from fastapi import UploadFile

from app.core.config import Settings
from app.core.exceptions import DocumentNotFoundError, NotImplementedStageError
from app.domain.entities import Document, Page
from app.domain.enums import DocumentStatus
from app.repositories.base import (
    ChunkRepository,
    DocumentRepository,
    ParseJobRepository,
)
from app.vector.base import SparseIndex, VectorRepository


class DocumentService:
    def __init__(
        self,
        documents: DocumentRepository,
        chunks: ChunkRepository,
        jobs: ParseJobRepository,
        vector: VectorRepository,
        sparse: SparseIndex,
        parse_queue,
        settings: Settings,
    ) -> None:
        self._documents = documents
        self._chunks = chunks
        self._jobs = jobs
        self._vector = vector
        self._sparse = sparse
        self._parse_queue = parse_queue
        self._settings = settings

    async def upload(self, files: Sequence[UploadFile]) -> list[dict]:
        """M1 落地：校验 → 落盘 → 建 Document(pending) + ParseJob(queued) → 入队。"""
        raise NotImplementedStageError("M1: 上传与解析任务")

    async def list(
        self,
        *,
        page: int,
        page_size: int,
        status: DocumentStatus | None = None,
        q: str | None = None,
    ) -> Page[Document]:
        return await self._documents.list(page=page, page_size=page_size, status=status, q=q)

    async def get(self, doc_id: UUID) -> Document:
        doc = await self._documents.get(doc_id)
        if doc is None:
            raise DocumentNotFoundError(f"文档不存在: {doc_id}")
        return doc

    async def delete(self, doc_id: UUID) -> None:
        await self.get(doc_id)
        await self._documents.delete(doc_id)
        await self._chunks.delete_by_document(doc_id)
        # M1: 删除后触发 vector/sparse rebuild 收敛索引

    async def reparse(self, doc_id: UUID) -> dict:
        raise NotImplementedStageError("M1: 重新解析")
