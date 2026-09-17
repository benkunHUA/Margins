"""DocumentService 测试：上传校验 / 删除收敛 / 重试入队。"""

import asyncio
import io
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi import UploadFile

from app.core.config import Settings
from app.core.exceptions import FileTooLargeError, InvalidFileTypeError
from app.domain.enums import DocumentStatus
from app.index.ports import IndexChangeSet, IndexRecord
from app.index.writer import IndexWriter
from app.repositories.memory.memory_repos import (
    InMemoryChunkRepository,
    InMemoryDocumentRepository,
    InMemoryParseJobRepository,
)
from app.services.document_service import DocumentService
from app.services.embedding import EmbeddingService
from tests.index.fakes import InMemoryIndexBackend


class FakeEmbeddings(EmbeddingService):
    async def embed_texts(self, texts):
        return [[1.0, 0.0]] * len(texts)

    async def embed_query(self, text):
        return [1.0, 0.0]


def _settings(tmp_path) -> Settings:
    return Settings(_env_file=None, data_dir=tmp_path)


@pytest.fixture
async def service(tmp_path):
    documents = InMemoryDocumentRepository()
    chunks = InMemoryChunkRepository()
    jobs = InMemoryParseJobRepository()
    queue: asyncio.Queue = asyncio.Queue()
    backend = InMemoryIndexBackend()
    svc = DocumentService(
        documents=documents,
        chunks=chunks,
        jobs=jobs,
        index_writer=IndexWriter(backend, FakeEmbeddings()),
        parse_queue=queue,
        settings=_settings(tmp_path),
        max_file_size_bytes=1024,
    )
    yield svc, documents, chunks, jobs, queue, backend


async def test_upload_validates_type(service) -> None:
    svc = service[0]
    with pytest.raises(InvalidFileTypeError):
        await svc.upload([UploadFile(filename="evil.exe", file=io.BytesIO(b"x"))])


async def test_upload_validates_size(service) -> None:
    svc = service[0]
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


async def test_delete_removes_index_and_document(service) -> None:
    svc, documents, _, _, _, backend = service
    results = await svc.upload([UploadFile(filename="a.md", file=io.BytesIO(b"# hello"))])
    doc = await documents.get(results[0]["document_id"])
    await backend.apply(
        IndexChangeSet(
            upserts=[
                IndexRecord(
                    chunk_id=uuid4(),
                    document_id=doc.id,
                    content="回购股份进展",
                    embedding=[1.0, 0.0],
                )
            ]
        )
    )

    await svc.delete(doc.id)

    assert await documents.get(doc.id) is None
    stats = await backend.stats()
    assert stats["chunks"] == 0  # 索引随文档删除一起收敛，无孤儿
    assert await backend.sparse.search("回购", 5) == []


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
