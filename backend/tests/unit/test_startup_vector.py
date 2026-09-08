"""容器启动向量重建策略测试：索引完整跳过、缺失才重建、失败不阻塞启动。"""

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
        loaded: set[str] | None = None,
        *,
        fail_rebuild: bool = False,
    ) -> None:
        self.loaded = loaded or set()
        self.fail_rebuild = fail_rebuild
        self.rebuild_calls = 0

    def loaded_ids(self) -> set[str]:
        return set(self.loaded)

    async def add(self, items):
        pass

    async def search(self, embedding, k):
        return []

    async def rebuild(self, chunks):
        self.rebuild_calls += 1
        if self.fail_rebuild:
            raise RuntimeError("embedding boom")
        self.loaded = {str(c.id) for c in chunks}

    async def save(self):
        pass

    async def load(self):
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


async def test_startup_skips_rebuild_when_all_ids_loaded(tmp_path) -> None:
    vector = FakeVector()
    container = await _make_container(tmp_path, vector)
    chunk_ids = {str(c.id) for c in await container.chunks.list_all()}
    vector.loaded = chunk_ids

    await container.startup()

    assert vector.rebuild_calls == 0


async def test_startup_survives_rebuild_failure(tmp_path) -> None:
    vector = FakeVector(fail_rebuild=True)
    container = await _make_container(tmp_path, vector)

    await container.startup()

    assert vector.rebuild_calls == 1
