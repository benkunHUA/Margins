"""Faiss 向量仓库测试（临时目录 + 确定性 fake embedding）。"""

from uuid import uuid4

from app.core.config import StorageConfig
from app.domain.entities import Chunk
from app.services.embedding import EmbeddingService
from app.vector.base import IndexableChunk
from app.vector.faiss_repo import FaissVectorRepository


class FakeEmbeddingService(EmbeddingService):
    def __init__(self) -> None:
        self._dim = 4

    async def embed_texts(self, texts):
        return [[float(i + 1) / 10, 0.0, 0.0, 0.0] for i in range(len(texts))]

    async def embed_query(self, text: str):
        return [0.9, 0.0, 0.0, 0.0]


def _chunk(text: str) -> Chunk:
    return Chunk(
        id=uuid4(),
        document_id=uuid4(),
        chunk_index=0,
        content=text,
        heading_path="h",
    )


def _repo(tmp_path, embeddings) -> FaissVectorRepository:
    config = StorageConfig(data_dir=tmp_path)
    return FaissVectorRepository(config, embeddings, dimension=4)


async def test_add_and_search(tmp_path) -> None:
    embeddings = FakeEmbeddingService()
    repo = _repo(tmp_path, embeddings)
    chunk = _chunk("hello")
    await repo.add([IndexableChunk(chunk=chunk, embedding=[0.9, 0.0, 0.0, 0.0])])

    results = await repo.search([0.8, 0.0, 0.0, 0.0], k=3)
    assert len(results) == 1
    assert results[0].chunk.id == chunk.id
    assert results[0].score > 0.9


async def test_empty_index_returns_empty(tmp_path) -> None:
    repo = _repo(tmp_path, FakeEmbeddingService())
    assert await repo.search([1.0, 0.0, 0.0, 0.0], k=5) == []


async def test_save_and_load_roundtrip(tmp_path) -> None:
    embeddings = FakeEmbeddingService()
    repo = _repo(tmp_path, embeddings)
    chunk = _chunk("persisted")
    await repo.add([IndexableChunk(chunk=chunk, embedding=[0.9, 0.0, 0.0, 0.0])])

    repo2 = _repo(tmp_path, embeddings)
    await repo2.load()
    results = await repo2.search([0.8, 0.0, 0.0, 0.0], k=3)
    assert results[0].chunk.id == chunk.id


async def test_rebuild_replaces_index(tmp_path) -> None:
    embeddings = FakeEmbeddingService()
    repo = _repo(tmp_path, embeddings)
    old = _chunk("old")
    new = _chunk("new")
    await repo.add([IndexableChunk(chunk=old, embedding=[0.9, 0.0, 0.0, 0.0])])
    await repo.rebuild([new])

    results = await repo.search([0.8, 0.0, 0.0, 0.0], k=3)
    assert len(results) == 1
    assert results[0].chunk.id == new.id
