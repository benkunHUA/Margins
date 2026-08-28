"""解析任务 Worker：进程内 asyncio 队列 + 重试状态机。"""

import asyncio
from datetime import UTC, datetime
from uuid import UUID

from app.core.config import QueueConfig, StorageConfig
from app.core.logging import get_logger
from app.domain.enums import DocumentStatus, ParseJobStatus
from app.repositories.base import DocumentRepository, ParseJobRepository
from app.services.indexing import IndexingPipeline
from app.services.parsing import MineruParser

logger = get_logger(__name__)


class ParseWorker:
    def __init__(
        self,
        queue: asyncio.Queue[UUID],
        parser: MineruParser,
        indexing: IndexingPipeline,
        documents: DocumentRepository,
        jobs: ParseJobRepository,
        config: QueueConfig,
        storage: StorageConfig,
    ) -> None:
        self._queue = queue
        self._parser = parser
        self._indexing = indexing
        self._documents = documents
        self._jobs = jobs
        self._config = config
        self._storage = storage

    async def run(self) -> None:
        semaphore = asyncio.Semaphore(self._config.concurrency)
        while True:
            doc_id = await self._queue.get()
            try:
                async with semaphore:
                    await self._process_one(doc_id)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("解析任务异常: %s", doc_id)
            finally:
                self._queue.task_done()

    async def _process_one(self, doc_id: UUID) -> None:
        doc = await self._documents.get(doc_id)
        if doc is None:
            return
        job = await self._jobs.get_by_document(doc_id)
        if job is None:
            return

        attempt = 0
        while True:
            now = datetime.now(UTC)
            doc.status = DocumentStatus.PARSING
            doc.updated_at = now
            await self._documents.update(doc)

            job.status = ParseJobStatus.RUNNING
            job.attempt = attempt
            job.started_at = now
            job.last_error = None
            await self._jobs.update(job)

            try:
                parsed = await self._parser.parse(doc.file_path, file_type=doc.file_type)
                parsed_dir = self._storage.parsed_dir
                await asyncio.to_thread(parsed_dir.mkdir, parents=True, exist_ok=True)
                markdown_path = parsed_dir / f"{doc.id}.md"
                await asyncio.to_thread(markdown_path.write_text, parsed.markdown, "utf-8")

                await self._indexing.run(
                    parsed.markdown,
                    document_id=doc.id,
                    doc_title=doc.filename,
                )

                doc.markdown_path = markdown_path
                doc.status = DocumentStatus.READY
                doc.parse_error = None
                doc.updated_at = datetime.now(UTC)
                await self._documents.update(doc)

                job.status = ParseJobStatus.SUCCEEDED
                job.finished_at = datetime.now(UTC)
                await self._jobs.update(job)
                return
            except Exception as exc:
                attempt += 1
                if attempt <= self._config.max_retries:
                    backoff = self._config.backoff_seconds[
                        min(attempt - 1, len(self._config.backoff_seconds) - 1)
                    ]
                    await asyncio.sleep(backoff)
                    continue
                doc.status = DocumentStatus.FAILED
                doc.parse_error = str(exc)
                doc.updated_at = datetime.now(UTC)
                await self._documents.update(doc)

                job.status = ParseJobStatus.FAILED
                job.last_error = str(exc)
                job.finished_at = datetime.now(UTC)
                await self._jobs.update(job)
                return
