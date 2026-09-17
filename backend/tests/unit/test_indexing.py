"""入库管线测试：真实分块器 + fake 向量化 + 真实 SQLite 索引后端。"""

from uuid import uuid4

import pytest

from app.core.exceptions import ParseFailedError
from app.index.sqlite_backend import SqliteIndexBackend
from app.index.writer import IndexWriter
from app.repositories.sql.database import run_migrations
from app.services.chunking import MarkdownChunker
from app.services.embedding import EmbeddingService
from app.services.indexing import IndexingPipeline

DIMENSION = 4


class FakeEmbeddingService(EmbeddingService):
    async def embed_texts(self, texts):
        return [[1.0 / (index + 1), 0.0, 0.0, 0.0] for index in range(len(texts))]

    async def embed_query(self, text):
        return [1.0, 0.0, 0.0, 0.0]


@pytest.fixture
async def pipeline(tmp_path):
    run_migrations(tmp_path)
    backend = SqliteIndexBackend(tmp_path / "margins.db", dimension=DIMENSION)
    await backend.initialize()
    writer = IndexWriter(backend, FakeEmbeddingService())
    yield IndexingPipeline(MarkdownChunker(), writer), backend
    await backend.close()


async def test_run_writes_chunks_fts_and_vectors(pipeline) -> None:
    indexing, backend = pipeline
    doc_id = uuid4()

    await indexing.run("# 标题\n\n正文内容", document_id=doc_id, doc_title="a.pdf")

    stats = await backend.stats()
    assert stats["chunks"] == stats["fts"] == stats["vectors"] > 0
    dense = await backend.dense.search([0.9, 0.0, 0.0, 0.0], k=5)
    assert any(item.chunk.document_id == doc_id for item in dense)
    assert dense[0].chunk.metadata["doc_title"] == "a.pdf"


async def test_run_reindexes_same_document_atomically(pipeline) -> None:
    """重解析必须替换旧块，三张表行数始终一致。"""
    indexing, backend = pipeline
    doc_id = uuid4()
    await indexing.run("# 旧标题\n\n旧内容：注册资本", document_id=doc_id)

    await indexing.run("# 华泰证券回购进展\n\n累计回购 707,939 股", document_id=doc_id)

    stats = await backend.stats()
    assert stats["chunks"] == stats["fts"] == stats["vectors"]
    assert await backend.sparse.search("注册资本", k=5) == []
    hits = await backend.sparse.search("回购 进展", k=5)
    assert hits and "707,939" in hits[0].chunk.content


async def test_empty_markdown_raises(pipeline) -> None:
    indexing, _ = pipeline
    with pytest.raises(ParseFailedError):
        await indexing.run("", document_id=uuid4())
