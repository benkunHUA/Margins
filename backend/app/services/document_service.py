"""文档生命周期服务。"""

from __future__ import annotations

import asyncio
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

import aiofiles
from fastapi import UploadFile

from app.core.config import Settings
from app.core.constants import MAX_FILE_SIZE_BYTES, SUPPORTED_FILE_TYPES
from app.core.exceptions import (
    DocumentNotFoundError,
    FileTooLargeError,
    InvalidFileTypeError,
)
from app.domain.entities import Chunk, Document, Page, ParseJob
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
        max_file_size_bytes: int = MAX_FILE_SIZE_BYTES,
    ) -> None:
        self._documents = documents
        self._chunks = chunks
        self._jobs = jobs
        self._vector = vector
        self._sparse = sparse
        self._parse_queue = parse_queue
        self._settings = settings
        self._max_file_size_bytes = max_file_size_bytes

    async def upload(self, files: Sequence[UploadFile]) -> list[dict]:
        results: list[dict] = []
        for file in files:
            filename = file.filename or "unnamed"
            ext = Path(filename).suffix.lower().lstrip(".")
            if ext not in SUPPORTED_FILE_TYPES:
                raise InvalidFileTypeError(f"不支持的文件类型: {ext}")

            content = await file.read()
            if len(content) > self._max_file_size_bytes:
                raise FileTooLargeError(f"文件超过大小上限: {filename}")

            doc_id = uuid4()
            upload_dir = self._settings.storage.upload_dir
            await asyncio.to_thread(upload_dir.mkdir, parents=True, exist_ok=True)
            dest = upload_dir / f"{doc_id}.{ext}"
            async with aiofiles.open(dest, "wb") as f:
                await f.write(content)

            now = datetime.now(UTC)
            doc = Document(
                id=doc_id,
                filename=filename,
                file_type=ext,
                file_size=len(content),
                file_path=dest,
                created_at=now,
                updated_at=now,
            )
            await self._documents.create(doc)
            await self._jobs.create(ParseJob(document_id=doc.id, queued_at=now))
            await self._parse_queue.put(doc.id)
            results.append(
                {"document_id": doc.id, "filename": doc.filename, "status": doc.status.value}
            )
        return results

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

    async def list_chunks(self, doc_id: UUID) -> list[Chunk]:
        await self.get(doc_id)
        return await self._chunks.list_by_document(doc_id)

    async def delete(self, doc_id: UUID) -> None:
        doc = await self.get(doc_id)
        await self._documents.delete(doc_id)
        await self._chunks.delete_by_document(doc_id)
        for path in (doc.file_path, doc.markdown_path):
            if path is not None:
                await asyncio.to_thread(_safe_unlink, path)
        remaining = await self._chunks.list_all()
        await self._vector.rebuild(remaining)
        # M3: 同步 sparse.rebuild

    async def reparse(self, doc_id: UUID) -> dict:
        doc = await self.get(doc_id)
        now = datetime.now(UTC)
        doc.status = DocumentStatus.PENDING
        doc.parse_error = None
        doc.updated_at = now
        await self._documents.update(doc)
        job = await self._jobs.create(ParseJob(document_id=doc.id, queued_at=now))
        await self._parse_queue.put(doc.id)
        return {"job_id": str(job.id), "status": job.status.value}


def _safe_unlink(path: Path) -> None:
    try:
        path.unlink(missing_ok=True)
    except OSError:
        pass
