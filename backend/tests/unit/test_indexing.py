"""入库管线测试：真实分块器 + fake 向量化 + 临时 Faiss + 内存 chunk 仓储。"""

from uuid import uuid4

import pytest

from app.core.config import StorageConfig
from app.core.exceptions import ParseFailedError
from app.repositories.memory.memory_repos import InMemoryChunkRepository
from app.services.chunking import MarkdownChunker
from app.services.embedding import EmbeddingService
from app.services.indexing import IndexingPipeline
from app.vector.faiss_repo import FaissVectorRepository


class FakeEmbeddingService(EmbeddingService):
    async def embed_texts(self, texts):
        return [[1.0 / (i + 1), 0.0, 0.0, 0.0] for i in range(len(texts))]

    async def embed_query(self, text):
        return [1.0, 0.0, 0.0, 0.0]


@pytest.fixture
async def pipeline(tmp_path):
    chunks = InMemoryChunkRepository()
    vector = FaissVectorRepository(
        StorageConfig(data_dir=tmp_path), FakeEmbeddingService(), dimension=4
    )
    pipeline = IndexingPipeline(MarkdownChunker(), FakeEmbeddingService(), vector, chunks)
    yield pipeline, chunks, vector


async def test_run_writes_chunks_and_vectors(pipeline) -> None:
    pipeline, chunks, vector = pipeline
    doc_id = uuid4()
    await pipeline.run("# 标题\n\n正文内容", document_id=doc_id)

    stored = await chunks.list_by_document(doc_id)
    assert len(stored) >= 1
    assert stored[0].document_id == doc_id

    results = await vector.search([0.9, 0.0, 0.0, 0.0], k=5)
    assert any(item.chunk.document_id == doc_id for item in results)


async def test_run_is_idempotent_for_same_document(pipeline) -> None:
    pipeline, chunks, _ = pipeline
    doc_id = uuid4()
    await pipeline.run("# 标题\n\n正文", document_id=doc_id)
    first_count = len(await chunks.list_by_document(doc_id))
    await pipeline.run("# 新标题\n\n新正文", document_id=doc_id)
    second = await chunks.list_by_document(doc_id)
    assert len(second) >= 1
    assert len(second) == first_count  # 先清后写，块数只与本次内容相关


async def test_empty_markdown_raises(pipeline) -> None:
    pipeline, _, _ = pipeline
    with pytest.raises(ParseFailedError):
        await pipeline.run("", document_id=uuid4())
