"""解析任务 Worker：进程内 asyncio 队列 + 重试状态机。"""

import asyncio
import shutil
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from app.core.config import ImageSummaryConfig, QueueConfig, StorageConfig
from app.core.logging import get_logger
from app.domain.entities import Document
from app.domain.enums import DocumentStatus, ParseJobStatus
from app.repositories.base import DocumentRepository, ParseJobRepository
from app.services.image_enrichment import (
    contains_image_placeholder,
    enrich_markdown_with_summaries,
)
from app.services.image_summarizer import ImageSummarizer
from app.services.indexing import IndexingPipeline
from app.services.parsing import MineruParser, ParsedDocument

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
        image_summarizer: ImageSummarizer | None = None,
        image_config: ImageSummaryConfig | None = None,
    ) -> None:
        self._queue = queue
        self._parser = parser
        self._indexing = indexing
        self._documents = documents
        self._jobs = jobs
        self._config = config
        self._storage = storage
        self._image_summarizer = image_summarizer
        self._image_config = image_config

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
                parsed_dir = self._storage.parsed_dir
                await asyncio.to_thread(parsed_dir.mkdir, parents=True, exist_ok=True)
                images_dir = self._images_dir(doc.id)
                if images_dir is not None:
                    await asyncio.to_thread(_clear_dir, images_dir)

                parsed = await self._parser.parse(
                    doc.file_path,
                    file_type=doc.file_type,
                    images_dir=images_dir,
                )
                markdown = parsed.markdown

                if (
                    self._should_summarize()
                    and not parsed.images
                    and contains_image_placeholder(markdown)
                ):
                    markdown, parsed = await self._upgrade_for_images(
                        doc, parsed, markdown, images_dir
                    )

                if parsed.images and self._should_summarize():
                    try:
                        markdown = await self._summarize_images(markdown, parsed.images)
                    except Exception:
                        logger.warning("图片文字总结失败，沿用原文继续入库", exc_info=True)

                markdown_path = parsed_dir / f"{doc.id}.md"
                await asyncio.to_thread(markdown_path.write_text, markdown, "utf-8")

                await self._indexing.run(
                    markdown,
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

    def _should_summarize(self) -> bool:
        return (
            self._image_config is not None
            and self._image_config.enabled
            and self._image_summarizer is not None
        )

    def _images_dir(self, doc_id: UUID) -> Path | None:
        if not self._should_summarize():
            return None
        return self._storage.parsed_dir / f"{doc_id}.images"

    async def _upgrade_for_images(
        self,
        doc: Document,
        parsed: ParsedDocument,
        markdown: str,
        images_dir: Path | None,
    ) -> tuple[str, ParsedDocument]:
        """flash 结果含图时升级 extract 取图；失败降级沿用 flash 结果。"""
        if not self._parser.supports_full_extract:
            logger.warning(
                "flash 结果含图片但 MINERU_API_TOKEN 未配置，跳过 extract 升级（图片不会入库）"
            )
            return markdown, parsed
        logger.info("flash 结果含图片，升级 extract 通道取图")
        try:
            upgraded = await self._parser.parse(
                doc.file_path,
                file_type=doc.file_type,
                images_dir=images_dir,
                force_extract=True,
            )
            return upgraded.markdown, upgraded
        except Exception:
            logger.warning("升级 extract 失败，沿用 flash markdown 继续入库", exc_info=True)
            return markdown, parsed

    async def _summarize_images(self, markdown: str, images: Sequence[Path]) -> str:
        assert self._image_config is not None
        assert self._image_summarizer is not None
        candidates = [
            path for path in images if path.stat().st_size >= self._image_config.min_bytes
        ][: self._image_config.max_images]
        if not candidates:
            logger.info("无可总结图片（全部小于 %d 字节）", self._image_config.min_bytes)
            return markdown
        summaries = await self._image_summarizer.summarize_images(candidates)
        by_name = {
            path.name: text for path, text in zip(candidates, summaries, strict=True)
        }
        enriched = enrich_markdown_with_summaries(markdown, by_name)
        logger.info(
            "图片文字总结完成：总结 %d 张，替换引用 %d 处，文末补充 %d 张",
            len(candidates),
            enriched.replaced,
            enriched.appended,
        )
        return enriched.markdown


def _clear_dir(directory: Path) -> None:
    """清空并重建目录（解析前清理上一轮图片，避免残留旧图）。"""
    directory.mkdir(parents=True, exist_ok=True)
    for child in directory.iterdir():
        if child.is_dir():
            shutil.rmtree(child, ignore_errors=True)
        else:
            child.unlink(missing_ok=True)
