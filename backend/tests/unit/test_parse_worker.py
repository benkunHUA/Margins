"""ParseWorker 测试：成功 / 重试后成功 / 重试耗尽。"""

import asyncio
from pathlib import Path

from app.core.config import QueueConfig, StorageConfig
from app.domain.entities import Document, ParseJob
from app.domain.enums import DocumentStatus, ParseJobStatus
from app.repositories.memory.memory_repos import (
    InMemoryDocumentRepository,
    InMemoryParseJobRepository,
)
from app.services.parsing import MineruParser, ParsedDocument
from app.workers.parse_worker import ParseWorker


class FakeParser(MineruParser):
    def __init__(self, failures: int = 0) -> None:
        self.failures = failures
        self.calls = 0

    async def parse(self, file_path: Path, *, file_type: str) -> ParsedDocument:
        self.calls += 1
        if self.calls <= self.failures:
            raise RuntimeError("mineru boom")
        return ParsedDocument(markdown="# ok")


class FakeIndexing:
    def __init__(self) -> None:
        self.runs: list[tuple[str, object]] = []

    async def run(self, markdown: str, *, document_id) -> None:
        self.runs.append((markdown, document_id))


def _config(max_retries: int = 2) -> QueueConfig:
    return QueueConfig(
        concurrency=1,
        max_retries=max_retries,
        backoff_seconds=(0.001, 0.001),
    )


async def _make_worker(tmp_path, parser: FakeParser, max_retries: int = 2):
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
