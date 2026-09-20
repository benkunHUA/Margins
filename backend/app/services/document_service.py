"""文档生命周期服务。"""

from __future__ import annotations

import asyncio
import shutil
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

import aiofiles
from fastapi import UploadFile

from app.core.config import Settings
from app.core.constants import MAX_FILE_SIZE_BYTES, SUPPORTED_FILE_TYPES
from app.core.exceptions import (
    ChunkNotFoundError,
    DocumentNotFoundError,
    FileTooLargeError,
    InvalidFileTypeError,
)
from app.domain.entities import (
    Chunk,
    ChunkContext,
    ChunkContextItem,
    Document,
    Page,
    ParseJob,
)
from app.domain.enums import DocumentStatus, ParseMode
from app.index.writer import IndexWriter
from app.repositories.base import (
    ChunkRepository,
    DocumentRepository,
    ParseJobRepository,
)


class DocumentService:
    def __init__(
        self,
        documents: DocumentRepository,
        chunks: ChunkRepository,
        jobs: ParseJobRepository,
        index_writer: IndexWriter,
        parse_queue,
        settings: Settings,
        max_file_size_bytes: int = MAX_FILE_SIZE_BYTES,
    ) -> None:
        self._documents = documents
        self._chunks = chunks
        self._jobs = jobs
        self._index_writer = index_writer
        self._parse_queue = parse_queue
        self._settings = settings
        self._max_file_size_bytes = max_file_size_bytes

    async def upload(
        self,
        files: Sequence[UploadFile],
        parse_mode: ParseMode = ParseMode.MINERU,
    ) -> list[dict]:
        results: list[dict] = []
        for file in files:
            filename = file.filename or "unnamed"
            ext = Path(filename).suffix.lower().lstrip(".")
            if ext not in SUPPORTED_FILE_TYPES:
                raise InvalidFileTypeError(f"不支持的文件类型: {ext}")
            effective = _effective_parse_mode(ext, parse_mode)

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
                parse_mode=effective,
                created_at=now,
                updated_at=now,
            )
            await self._documents.create(doc)
            await self._jobs.create(ParseJob(document_id=doc.id, queued_at=now))
            await self._parse_queue.put(doc.id)
            results.append(
                {
                    "document_id": doc.id,
                    "filename": doc.filename,
                    "status": doc.status.value,
                    "parse_mode": effective.value,
                }
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

    async def get_chunk_context(self, chunk_id: UUID, *, radius: int = 1) -> ChunkContext:
        """取某个 chunk 及其前后邻居，供引用弹框预览。"""
        found = await self._chunks.get_many([chunk_id])
        if not found:
            raise ChunkNotFoundError(f"分块不存在: {chunk_id}")
        focus = found[0]

        doc = await self._documents.get(focus.document_id)
        doc_title = doc.filename if doc is not None else str(focus.document_id)

        # list_by_document 已按 chunk_index 升序（SQL 实现显式 order_by）
        siblings = await self._chunks.list_by_document(focus.document_id)
        position = next(
            (index for index, chunk in enumerate(siblings) if chunk.id == focus.id),
            None,
        )
        if position is None:
            window = [focus]  # 兜底：理论上不会发生
        else:
            window = siblings[max(0, position - radius) : position + radius + 1]

        return ChunkContext(
            chunk_id=focus.id,
            document_id=focus.document_id,
            doc_title=doc_title,
            heading_path=focus.heading_path,
            chunk_index=focus.chunk_index,
            chunk_total=len(siblings),
            radius=radius,
            items=[
                ChunkContextItem(
                    chunk_id=chunk.id,
                    chunk_index=chunk.chunk_index,
                    heading_path=chunk.heading_path,
                    content=chunk.content,
                    is_focus=chunk.id == focus.id,
                )
                for chunk in window
            ],
        )

    async def delete(self, doc_id: UUID) -> None:
        doc = await self.get(doc_id)
        # 先删索引三表（chunks + FTS + 向量），再删文档行，避免留下孤儿索引
        await self._index_writer.delete_document(doc_id)
        await self._documents.delete(doc_id)
        for path in (doc.file_path, doc.markdown_path):
            if path is not None:
                await asyncio.to_thread(_safe_unlink, path)
        images_dir = self._settings.storage.parsed_dir / f"{doc.id}.images"
        await asyncio.to_thread(_safe_rmtree, images_dir)

    async def reparse(
        self,
        doc_id: UUID,
        parse_mode: ParseMode | None = None,
    ) -> dict:
        doc = await self.get(doc_id)
        if parse_mode is not None:
            doc.parse_mode = _effective_parse_mode(doc.file_type, parse_mode)
            doc.updated_at = datetime.now(UTC)
            await self._documents.update(doc)
        now = datetime.now(UTC)
        doc.status = DocumentStatus.PENDING
        doc.parse_error = None
        doc.updated_at = now
        await self._documents.update(doc)
        job = await self._jobs.create(ParseJob(document_id=doc.id, queued_at=now))
        await self._parse_queue.put(doc.id)
        return {
            "job_id": str(job.id),
            "status": job.status.value,
            "parse_mode": doc.parse_mode.value,
        }


def _safe_unlink(path: Path) -> None:
    try:
        path.unlink(missing_ok=True)
    except OSError:
        pass


def _safe_rmtree(path: Path) -> None:
    shutil.rmtree(path, ignore_errors=True)


def _effective_parse_mode(file_type: str, chosen: ParseMode) -> ParseMode:
    if file_type in ("txt", "md"):
        return ParseMode.PLAIN_TEXT
    if file_type == "pdf":
        return chosen
    return ParseMode.MINERU
