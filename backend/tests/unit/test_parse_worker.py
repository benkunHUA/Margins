"""ParseWorker 测试：成功 / 重试后成功 / 重试耗尽。"""

import asyncio
from pathlib import Path

from app.core.config import ImageSummaryConfig, QueueConfig, StorageConfig
from app.domain.entities import Document, ParseJob
from app.domain.enums import DocumentStatus, ParseJobStatus, ParseMode
from app.repositories.memory.memory_repos import (
    InMemoryDocumentRepository,
    InMemoryParseJobRepository,
)
from app.services.image_summarizer import ImageSummarizer
from app.services.parsing import DocumentParser, ParsedDocument
from app.workers.parse_worker import ParseWorker


class FakeParser(DocumentParser):
    def __init__(self, failures: int = 0) -> None:
        self.failures = failures
        self.calls = 0
        self.cache_dirs: list[Path | None] = []

    async def parse(
        self,
        file_path: Path,
        *,
        file_type: str,
        images_dir: Path | None = None,
        force_extract: bool = False,
        cache_dir: Path | None = None,
    ) -> ParsedDocument:
        self.calls += 1
        self.cache_dirs.append(cache_dir)
        if cache_dir is not None:
            # 模拟分段解析写入段级缓存
            cache_dir.mkdir(parents=True, exist_ok=True)
            (cache_dir / "part-1-200.json").write_text("{}", encoding="utf-8")
        if self.calls <= self.failures:
            raise RuntimeError("mineru boom")
        return ParsedDocument(markdown="# ok")


class FakeIndexing:
    def __init__(self) -> None:
        self.runs: list[tuple[str, object]] = []

    async def run(self, markdown: str, *, document_id, doc_title: str | None = None) -> None:
        self.runs.append((markdown, document_id))


def _config(max_retries: int = 2) -> QueueConfig:
    return QueueConfig(
        concurrency=1,
        max_retries=max_retries,
        backoff_seconds=(0.001, 0.001),
    )


async def _make_worker(
    tmp_path,
    parser: FakeParser,
    max_retries: int = 2,
    *,
    image_summarizer=None,
    image_config=None,
):
    documents = InMemoryDocumentRepository()
    jobs = InMemoryParseJobRepository()
    queue: asyncio.Queue = asyncio.Queue()
    doc = Document(filename="a.md", file_type="md", file_size=1, file_path=tmp_path / "a.md")
    doc = await documents.create(doc)
    await jobs.create(ParseJob(document_id=doc.id))
    await queue.put(doc.id)
    worker = ParseWorker(
        queue=queue,
        parser=parser,
        indexing=FakeIndexing(),
        documents=documents,
        jobs=jobs,
        config=_config(max_retries),
        storage=StorageConfig(data_dir=tmp_path),
        image_summarizer=image_summarizer,
        image_config=image_config,
    )
    return worker, documents, jobs, doc


async def test_success_marks_ready_and_writes_markdown(tmp_path) -> None:
    worker, documents, jobs, doc = await _make_worker(tmp_path, FakeParser())
    await worker._process_one(doc.id)

    updated = await documents.get(doc.id)
    assert updated.status == DocumentStatus.READY
    assert updated.markdown_path is not None
    assert Path(updated.markdown_path).read_text(encoding="utf-8") == "# ok"
    job = await jobs.get_by_document(doc.id)
    assert job.status == ParseJobStatus.SUCCEEDED


async def test_retries_then_succeeds(tmp_path) -> None:
    parser = FakeParser(failures=2)
    worker, documents, jobs, doc = await _make_worker(tmp_path, parser, max_retries=2)
    await worker._process_one(doc.id)

    assert parser.calls == 3
    assert (await documents.get(doc.id)).status == DocumentStatus.READY
    assert (await jobs.get_by_document(doc.id)).status == ParseJobStatus.SUCCEEDED


async def test_exhausted_retries_marks_failed(tmp_path) -> None:
    parser = FakeParser(failures=99)
    worker, documents, jobs, doc = await _make_worker(tmp_path, parser, max_retries=2)
    await worker._process_one(doc.id)

    assert (await documents.get(doc.id)).status == DocumentStatus.FAILED
    job = await jobs.get_by_document(doc.id)
    assert job.status == ParseJobStatus.FAILED
    assert "mineru boom" in (job.last_error or "")


class SequenceParser(DocumentParser):
    """按调用顺序返回预置结果；None 表示该次调用抛错。"""

    def __init__(self, results: list[ParsedDocument | None], *, can_extract: bool = True) -> None:
        self.results = list(results)
        self.can_extract = can_extract
        self.calls: list[dict] = []

    @property
    def supports_full_extract(self) -> bool:
        return self.can_extract

    async def parse(
        self,
        file_path: Path,
        *,
        file_type: str,
        images_dir: Path | None = None,
        force_extract: bool = False,
        cache_dir: Path | None = None,
    ) -> ParsedDocument:
        self.calls.append({"images_dir": images_dir, "force_extract": force_extract})
        result = self.results.pop(0)
        if result is None:
            raise RuntimeError("extract boom")
        return result


class FakeImageSummarizer(ImageSummarizer):
    def __init__(
        self,
        *,
        text: str = "这是一张柱状图，数值逐年上升。",
        error: Exception | None = None,
    ) -> None:
        self.text = text
        self.error = error
        self.calls: list[list[Path]] = []

    async def summarize_images(self, images):
        self.calls.append(list(images))
        if self.error is not None:
            raise self.error
        return [self.text] * len(images)


class SpyParser(DocumentParser):
    def __init__(self, name: str) -> None:
        self.name = name
        self.calls = 0

    async def parse(
        self,
        file_path: Path,
        *,
        file_type: str,
        images_dir: Path | None = None,
        force_extract: bool = False,
        cache_dir: Path | None = None,
    ) -> ParsedDocument:
        self.calls += 1
        return ParsedDocument(markdown=f"#{self.name}")


async def _make_route_worker(tmp_path, mineru: SpyParser, plain: SpyParser):
    documents = InMemoryDocumentRepository()
    jobs = InMemoryParseJobRepository()
    queue: asyncio.Queue = asyncio.Queue()
    worker = ParseWorker(
        queue=queue,
        parser=mineru,
        plain_parser=plain,
        indexing=FakeIndexing(),
        documents=documents,
        jobs=jobs,
        config=_config(1),
        storage=StorageConfig(data_dir=tmp_path),
    )
    return worker, documents, jobs


async def _seed(documents, jobs, *, file_type: str, parse_mode: ParseMode):
    doc = await documents.create(
        Document(
            filename=f"a.{file_type}",
            file_type=file_type,
            file_size=1,
            file_path=Path(f"a.{file_type}"),
            parse_mode=parse_mode,
        )
    )
    await jobs.create(ParseJob(document_id=doc.id))
    return doc


async def test_worker_routes_txt_to_plain_parser(tmp_path) -> None:
    mineru = SpyParser("mineru")
    plain = SpyParser("plain")
    worker, documents, jobs = await _make_route_worker(tmp_path, mineru, plain)
    doc = await _seed(documents, jobs, file_type="txt", parse_mode=ParseMode.MINERU)

    await worker._process_one(doc.id)

    assert plain.calls == 1 and mineru.calls == 0


async def test_worker_routes_pdf_plain_mode_to_plain_parser(tmp_path) -> None:
    mineru = SpyParser("mineru")
    plain = SpyParser("plain")
    worker, documents, jobs = await _make_route_worker(tmp_path, mineru, plain)
    doc = await _seed(documents, jobs, file_type="pdf", parse_mode=ParseMode.PLAIN_TEXT)

    await worker._process_one(doc.id)

    assert plain.calls == 1 and mineru.calls == 0


async def test_worker_routes_pdf_mineru_to_mineru_parser(tmp_path) -> None:
    mineru = SpyParser("mineru")
    plain = SpyParser("plain")
    worker, documents, jobs = await _make_route_worker(tmp_path, mineru, plain)
    doc = await _seed(documents, jobs, file_type="pdf", parse_mode=ParseMode.MINERU)

    await worker._process_one(doc.id)

    assert mineru.calls == 1 and plain.calls == 0


def _image_summary_config(**kwargs) -> ImageSummaryConfig:
    values = {"enabled": True, "max_images": 10, "min_bytes": 5120}
    values.update(kwargs)
    return ImageSummaryConfig(**values)


def _write_image(tmp_path: Path, name: str, size: int = 6000) -> Path:
    p = tmp_path / "images" / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(b"x" * size)
    return p


async def test_flash_placeholder_upgrades_to_extract_then_indexes_summary(tmp_path) -> None:
    flash = ParsedDocument(markdown="# 标题\n\n<!-- image-->\n\n正文")
    image = _write_image(tmp_path, "chart.png")
    extract = ParsedDocument(
        markdown="# 标题\n\n![](images/chart.png)\n\n正文",
        images=[image],
    )
    parser = SequenceParser([flash, extract])
    summarizer = FakeImageSummarizer()
    worker, documents, jobs, doc = await _make_worker(
        tmp_path,
        parser,
        image_summarizer=summarizer,
        image_config=_image_summary_config(),
    )

    await worker._process_one(doc.id)

    assert parser.calls[0]["force_extract"] is False
    assert parser.calls[1]["force_extract"] is True
    assert parser.calls[1]["images_dir"] is not None
    assert summarizer.calls == [[image]]
    updated = await documents.get(doc.id)
    assert updated.status == DocumentStatus.READY
    content = Path(updated.markdown_path).read_text(encoding="utf-8")
    assert "这是一张柱状图" in content
    assert "![](images/chart.png)" not in content
    assert worker._indexing.runs[0][0] == content


async def test_no_placeholder_keeps_flash_single_call(tmp_path) -> None:
    parser = SequenceParser([ParsedDocument(markdown="# 纯文字")])
    summarizer = FakeImageSummarizer()
    worker, documents, jobs, doc = await _make_worker(
        tmp_path,
        parser,
        image_summarizer=summarizer,
        image_config=_image_summary_config(),
    )

    await worker._process_one(doc.id)

    assert len(parser.calls) == 1
    assert parser.calls[0]["force_extract"] is False
    assert summarizer.calls == []
    assert (await documents.get(doc.id)).status == DocumentStatus.READY


async def test_placeholder_without_token_skips_upgrade(tmp_path) -> None:
    parser = SequenceParser([ParsedDocument(markdown="<!-- image-->\n\n正文")], can_extract=False)
    worker, documents, jobs, doc = await _make_worker(
        tmp_path,
        parser,
        image_summarizer=FakeImageSummarizer(),
        image_config=_image_summary_config(),
    )

    await worker._process_one(doc.id)

    assert len(parser.calls) == 1
    assert (await documents.get(doc.id)).status == DocumentStatus.READY


async def test_upgrade_failure_falls_back_to_flash_markdown(tmp_path) -> None:
    flash = ParsedDocument(markdown="# 标题\n\n<!-- image-->\n\n正文")
    parser = SequenceParser([flash, None])
    worker, documents, jobs, doc = await _make_worker(
        tmp_path,
        parser,
        image_summarizer=FakeImageSummarizer(),
        image_config=_image_summary_config(),
    )

    await worker._process_one(doc.id)

    assert len(parser.calls) == 2
    updated = await documents.get(doc.id)
    assert updated.status == DocumentStatus.READY
    assert updated.parse_error is None
    assert "# 标题" in worker._indexing.runs[0][0]


async def test_summarize_respects_min_bytes_and_max_images(tmp_path) -> None:
    image_a = _write_image(tmp_path, "a.png", size=6000)
    image_b = _write_image(tmp_path, "b.png", size=6000)
    image_c = _write_image(tmp_path, "c.png", size=100)
    parsed = ParsedDocument(
        markdown="![](images/a.png)\n\n![](images/b.png)\n\n![](images/c.png)",
        images=[image_a, image_b, image_c],
    )
    parser = SequenceParser([parsed])
    summarizer = FakeImageSummarizer()
    worker, documents, jobs, doc = await _make_worker(
        tmp_path,
        parser,
        image_summarizer=summarizer,
        image_config=_image_summary_config(max_images=1),
    )

    await worker._process_one(doc.id)

    assert summarizer.calls == [[image_a]]
    indexed = worker._indexing.runs[0][0]
    assert "这是一张柱状图" in indexed
    assert "b.png" in indexed and "c.png" in indexed


async def test_summary_failure_keeps_original_markdown(tmp_path) -> None:
    image = _write_image(tmp_path, "chart.png")
    original = "# 标题\n\n![](images/chart.png)\n\n正文"
    parser = SequenceParser([ParsedDocument(markdown=original, images=[image])])
    summarizer = FakeImageSummarizer(error=RuntimeError("vlm down"))
    worker, documents, jobs, doc = await _make_worker(
        tmp_path,
        parser,
        image_summarizer=summarizer,
        image_config=_image_summary_config(),
    )

    await worker._process_one(doc.id)

    updated = await documents.get(doc.id)
    assert updated.status == DocumentStatus.READY
    assert updated.parse_error is None
    assert worker._indexing.runs[0][0] == original


async def test_worker_clears_parts_cache_after_success(tmp_path) -> None:
    """解析成功后段级缓存应被清理（合并结果已落盘，不再需要分段中间产物）。"""
    parser = FakeParser()
    worker, _, _, doc = await _make_worker(tmp_path, parser)
    parts_cache = tmp_path / "parsed" / f"{doc.id}.parts"

    await worker._process_one(doc.id)

    assert parser.cache_dirs == [parts_cache]
    assert not parts_cache.exists()


async def test_worker_keeps_parts_cache_when_parse_fails(tmp_path) -> None:
    """重试耗尽仍失败时保留段级缓存，便于后续只补跑失败段。"""
    parser = FakeParser(failures=99)
    worker, documents, jobs, doc = await _make_worker(tmp_path, parser, max_retries=1)
    parts_cache = tmp_path / "parsed" / f"{doc.id}.parts"

    await worker._process_one(doc.id)

    updated = await documents.get(doc.id)
    assert updated.status == DocumentStatus.FAILED
    assert parts_cache.is_dir()
