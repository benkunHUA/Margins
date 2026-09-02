"""DocumentService 测试：上传校验 / 删除收敛 / 重试入队。"""

import asyncio
import io
from pathlib import Path

import pytest
from fastapi import UploadFile

from app.core.config import Settings
from app.core.exceptions import FileTooLargeError, InvalidFileTypeError
from app.domain.entities import Chunk
from app.domain.enums import DocumentStatus
from app.repositories.memory.memory_repos import (
    InMemoryChunkRepository,
    InMemoryDocumentRepository,
    InMemoryParseJobRepository,
)
from app.services.document_service import DocumentService


class FakeVector:
    def __init__(self) -> None:
        self.rebuild_calls = 0

    async def rebuild(self, chunks) -> None:
        self.rebuild_calls += 1


class FakeSparse:
    def __init__(self) -> None:
        self.rebuild_calls = 0

    async def rebuild(self, chunks) -> None:
        self.rebuild_calls += 1


def _settings(tmp_path) -> Settings:
    return Settings(_env_file=None, data_dir=tmp_path)


@pytest.fixture
async def service(tmp_path):
    documents = InMemoryDocumentRepository()
    chunks = InMemoryChunkRepository()
    jobs = InMemoryParseJobRepository()
    queue: asyncio.Queue = asyncio.Queue()
    vector = FakeVector()
    svc = DocumentService(
        documents=documents,
        chunks=chunks,
        jobs=jobs,
        vector=vector,
        sparse=FakeSparse(),
        parse_queue=queue,
        settings=_settings(tmp_path),
        max_file_size_bytes=1024,
    )
    yield svc, documents, chunks, jobs, queue, vector


async def test_upload_validates_type(service) -> None:
    svc, _, _, _, _, _ = service
    with pytest.raises(InvalidFileTypeError):
        await svc.upload([UploadFile(filename="evil.exe", file=io.BytesIO(b"x"))])


async def test_upload_validates_size(service) -> None:
    svc, _, _, _, _, _ = service
    with pytest.raises(FileTooLargeError):
        await svc.upload([UploadFile(filename="big.pdf", file=io.BytesIO(b"x" * 2048))])


async def test_upload_saves_file_and_enqueues(service) -> None:
    svc, documents, _, _, queue, _ = service
    results = await svc.upload([UploadFile(filename="a.md", file=io.BytesIO(b"# hello"))])

    assert len(results) == 1
    doc = await documents.get(results[0]["document_id"])
    assert doc.status == DocumentStatus.PENDING
    assert Path(doc.file_path).read_text(encoding="utf-8") == "# hello"
    assert await queue.get() == doc.id


async def test_delete_removes_chunks_and_rebuilds(service) -> None:
    svc, documents, chunks, _, _, vector = service
    results = await svc.upload([UploadFile(filename="a.md", file=io.BytesIO(b"# hello"))])
    doc = await documents.get(results[0]["document_id"])
    await chunks.add_many([Chunk(document_id=doc.id, chunk_index=0, content="x")])

    await svc.delete(doc.id)
    assert await documents.get(doc.id) is None
    assert await chunks.list_by_document(doc.id) == []
    assert vector.rebuild_calls == 1


async def test_reparse_resets_and_enqueues(service) -> None:
    svc, documents, _, _, queue, _ = service
    results = await svc.upload([UploadFile(filename="a.md", file=io.BytesIO(b"# hello"))])
    doc = await documents.get(results[0]["document_id"])

    job = await svc.reparse(doc.id)
    updated = await documents.get(doc.id)
    assert updated.status == DocumentStatus.PENDING
    assert job["status"] == "queued"
    assert await queue.get() == doc.id


async def test_delete_removes_images_dir(service) -> None:
    svc, documents, _, _, _, _ = service
    results = await svc.upload([UploadFile(filename="a.md", file=io.BytesIO(b"# hello"))])
    doc = await documents.get(results[0]["document_id"])
    # data/uploads/<id>.md → data/parsed/<id>.images
    images_dir = Path(doc.file_path).parent.parent / "parsed" / f"{doc.id}.images"
    images_dir.mkdir(parents=True, exist_ok=True)
    (images_dir / "chart.png").write_bytes(b"x")

    await svc.delete(doc.id)

    assert not images_dir.exists()
