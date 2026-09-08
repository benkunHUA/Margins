"""容器启动向量对账测试：faiss_id 精确集合、NULL 补号、失败不阻塞。"""

from uuid import uuid4

from app.core.config import Settings
from app.core.container import ServiceContainer
from app.domain.entities import Chunk
from app.services.embedding import EmbeddingService
from app.vector.base import VectorRepository


class FakeEmbeddings(EmbeddingService):
    async def embed_query(self, text):
        return [1.0, 0.0]

    async def embed_texts(self, texts):
        return [[1.0, 0.0]] * len(texts)


class FakeVector(VectorRepository):
    def __init__(
        self,
        loaded: set[int] | None = None,
        *,
        fail_rebuild: bool = False,
    ) -> None:
        self.loaded = loaded if loaded is not None else set()
        self.fail_rebuild = fail_rebuild
        self.rebuild_calls = 0

    def loaded_ids(self) -> set[int]:
        return set(self.loaded)

    async def add(self, items):
        pass

    async def search(self, embedding, k):
        return []

    async def rebuild(self, chunks):
        self.rebuild_calls += 1
        if self.fail_rebuild:
            raise RuntimeError("embedding boom")
        self.loaded = {c.faiss_id for c in chunks if c.faiss_id is not None}

    async def save(self):
        pass

    async def load(self):
        pass

    async def remove(self, faiss_ids):
        pass


async def _make_container(tmp_path, vector: FakeVector) -> ServiceContainer:
    settings = Settings(
        _env_file=None,
        data_dir=tmp_path,
        dashscope_api_key="test-key",
    )
    container = ServiceContainer(
        settings,
        repositories="memory",
        start_worker=False,
        vector=vector,
        embeddings=FakeEmbeddings(),
    )
    for index in range(2):
        await container.chunks.add_many(
            [
                Chunk(
                    document_id=uuid4(),
                    chunk_index=index,
                    content=f"内容 {index}",
                )
            ]
        )
    return container


async def test_startup_rebuilds_when_index_missing(tmp_path) -> None:
    vector = FakeVector()
    container = await _make_container(tmp_path, vector)

    await container.startup()

    assert vector.rebuild_calls == 1


async def test_startup_skips_rebuild_when_ids_match(tmp_path) -> None:
    vector = FakeVector()
    container = await _make_container(tmp_path, vector)
    vector.loaded = {c.faiss_id for c in await container.chunks.list_all()}

    await container.startup()

    assert vector.rebuild_calls == 0


async def test_startup_rebuilds_when_index_has_stale_extra_ids(tmp_path) -> None:
    vector = FakeVector()
    container = await _make_container(tmp_path, vector)
    chunk_ids = {c.faiss_id for c in await container.chunks.list_all()}
    vector.loaded = chunk_ids | {99999}  # 索引含 DB 之外的孤儿

    await container.startup()

    assert vector.rebuild_calls == 1


async def test_startup_survives_rebuild_failure(tmp_path) -> None:
    vector = FakeVector(fail_rebuild=True)
    container = await _make_container(tmp_path, vector)

    await container.startup()

    assert vector.rebuild_calls == 1


async def test_startup_allocates_missing_faiss_ids_then_rebuilds(tmp_path) -> None:
    vector = FakeVector()
    container = await _make_container(tmp_path, vector)
    for chunk in await container.chunks.list_all():
        chunk.faiss_id = None  # 模拟升级遗留 NULL 行

    await container.startup()

    assert vector.rebuild_calls == 1
    rows = await container.chunks.list_all()
    assert all(c.faiss_id is not None for c in rows)
