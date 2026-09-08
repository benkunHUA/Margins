"""Faiss IndexIDMap 仓储测试（临时目录 + fake embedding + 内存 chunk 仓储）。"""

from uuid import uuid4

from app.core.config import StorageConfig
from app.domain.entities import Chunk
from app.repositories.memory.memory_repos import InMemoryChunkRepository
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


def _make(tmp_path) -> tuple[FaissVectorRepository, InMemoryChunkRepository]:
    chunks = InMemoryChunkRepository()
    repo = FaissVectorRepository(
        StorageConfig(data_dir=tmp_path),
        FakeEmbeddingService(),
        dimension=4,
        chunks=chunks,
    )
    return repo, chunks


async def _seed(repo, chunks, texts) -> list[Chunk]:
    created = [_chunk(text) for text in texts]
    await chunks.add_many(created)
    await repo.add(
        [
            IndexableChunk(chunk=chunk, embedding=[0.9 - i * 0.2, 0.0, 0.0, 0.0])
            for i, chunk in enumerate(created)
        ]
    )
    return created


async def test_add_requires_faiss_id(tmp_path) -> None:
    repo, _ = _make(tmp_path)
    chunk = _chunk("no-id")
    try:
        await repo.add([IndexableChunk(chunk=chunk, embedding=[0.9, 0.0, 0.0, 0.0])])
    except ValueError:
        return
    raise AssertionError("缺少 faiss_id 时应报错")


async def test_add_and_search_returns_chunk_by_id(tmp_path) -> None:
    repo, chunks = _make(tmp_path)
    created = await _seed(repo, chunks, ["hello"])

    results = await repo.search([0.8, 0.0, 0.0, 0.0], k=3)
    assert len(results) == 1
    assert results[0].chunk.id == created[0].id
    assert results[0].score > 0.9


async def test_save_and_load_roundtrip_preserves_ids(tmp_path) -> None:
    repo, chunks = _make(tmp_path)
    created = await _seed(repo, chunks, ["persisted"])

    repo2, chunks2 = _make(tmp_path)
    chunks2._items = dict(chunks._items)
    await repo2.load()
    assert repo2.loaded_ids() == {c.faiss_id for c in created}
    results = await repo2.search([0.8, 0.0, 0.0, 0.0], k=3)
    assert results[0].chunk.id == created[0].id


async def test_remove_ids_removes_vector(tmp_path) -> None:
    repo, chunks = _make(tmp_path)
    created = await _seed(repo, chunks, ["a", "b"])

    await repo.remove([created[0].faiss_id])

    results = await repo.search([0.8, 0.0, 0.0, 0.0], k=5)
    assert [r.chunk.id for r in results] == [created[1].id]


async def test_rebuild_replaces_index(tmp_path) -> None:
    repo, chunks = _make(tmp_path)
    await _seed(repo, chunks, ["old"])
    new_chunks = [_chunk("new")]
    await chunks.add_many(new_chunks)

    await repo.rebuild(new_chunks)

    results = await repo.search([0.8, 0.0, 0.0, 0.0], k=3)
    assert [r.chunk.id for r in results] == [new_chunks[0].id]


async def test_load_old_flat_index_marks_stale(tmp_path) -> None:
    import faiss

    config = StorageConfig(data_dir=tmp_path)
    config.faiss_index_dir.mkdir(parents=True, exist_ok=True)
    faiss.write_index(faiss.IndexFlatIP(4), str(config.faiss_index_dir / "index.faiss"))

    repo, _ = _make(tmp_path)
    await repo.load()

    assert repo.needs_rebuild is True
