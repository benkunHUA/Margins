"""EvalRunner 集成测试：fake 组件跑完整一轮，校验指标与逐题明细。"""

import pytest

from app.core.config import Settings
from app.domain.entities import (
    Chunk,
    Document,
    EvalDataset,
    EvalDatasetPayload,
    EvalItemPayload,
    EvalRun,
    EvalRunConfig,
)
from app.domain.enums import EvalItemStatus, EvalRunStatus
from app.repositories.memory.memory_repos import (
    InMemoryChunkRepository,
    InMemoryDocumentRepository,
    InMemoryEvalDatasetRepository,
    InMemoryEvalRunItemRepository,
    InMemoryEvalRunRepository,
)
from app.services.embedding import EmbeddingService
from app.services.eval.runner import EvalRunner
from app.services.llm import LLMClient
from app.services.reranking import Reranker
from app.vector.base import ScoredChunk, VectorRepository
from app.vector.fusion import RRFFusion
from app.vector.sparse import BM25SparseIndex


class FakeEmbeddings(EmbeddingService):
    async def embed_texts(self, texts):
        return [[1.0, 0.0]] * len(texts)

    async def embed_query(self, text):
        return [1.0, 0.0]


class FakeVector(VectorRepository):
    def __init__(self, chunks: list[Chunk]) -> None:
        self.chunks = chunks

    async def search(self, embedding, k):
        return [
            ScoredChunk(chunk=chunk, score=0.9 - index * 0.1)
            for index, chunk in enumerate(self.chunks[:k])
        ]

    async def add(self, items):
        pass

    async def rebuild(self, chunks):
        pass

    async def save(self):
        pass

    async def load(self):
        pass


class FakeReranker(Reranker):
    async def rerank(self, query, candidates, *, top_n, threshold):
        return list(candidates)[:top_n]


class FakeLLM(LLMClient):
    async def stream(self, messages):
        yield "答案 [1]"

    async def complete(self, messages):
        return "答案 [1]"


@pytest.fixture
async def env(tmp_path):
    documents = InMemoryDocumentRepository()
    chunks = InMemoryChunkRepository()
    datasets = InMemoryEvalDatasetRepository()
    runs = InMemoryEvalRunRepository()
    items = InMemoryEvalRunItemRepository()

    doc = await documents.create(
        Document(
            filename="a.pdf",
            file_type="pdf",
            file_size=1,
            file_path=tmp_path / "a.pdf",
        )
    )
    target = Chunk(document_id=doc.id, chunk_index=0, content="回购价格上限 40.2 元/股")
    other = Chunk(document_id=doc.id, chunk_index=1, content="无关内容")
    await chunks.add_many([target, other])

    payload = EvalDatasetPayload(
        name="小集",
        items=[
            EvalItemPayload(
                id="q1",
                question="价格上限？",
                category="single_doc_fact",
                gold=[{"doc_title": "a.pdf", "keywords": ["40.2 元/股"]}],
            ),
            EvalItemPayload(
                id="q2",
                question="不存在的问题？",
                category="single_doc_fact",
                gold=[{"doc_title": "a.pdf", "keywords": ["不存在的关键词"]}],
            ),
        ],
    )
    dataset = await datasets.create(
        EvalDataset(name="小集", payload=payload, item_count=2)
    )
    run = await runs.create(
        EvalRun(dataset_id=dataset.id, configs=[EvalRunConfig()], progress_total=2)
    )

    runner = EvalRunner(
        datasets=datasets,
        runs=runs,
        items=items,
        documents=documents,
        chunks=chunks,
        embeddings=FakeEmbeddings(),
        vector=FakeVector([target, other]),
        sparse=BM25SparseIndex(),
        fusion=RRFFusion(),
        reranker=FakeReranker(),
        llm_client=FakeLLM(),
        settings=Settings(_env_file=None, data_dir=tmp_path, dashscope_api_key="k"),
    )
    await runner._execute(run.id)
    return runs, items, run


async def test_runner_completes_and_aggregates(env) -> None:
    runs, items, run = env
    stored = await runs.get(run.id)
    assert stored.status == EvalRunStatus.SUCCEEDED
    assert stored.progress_done == 2
    metrics = stored.metrics["0"]
    assert metrics["recall@10"] == 1.0  # q1 命中；q2 为 invalid，不计入主指标
    assert metrics["invalid"] == 1

    page = await items.list(run_id=run.id, page=1, page_size=10)
    statuses = {item.question_id: item.item_status for item in page.items}
    assert statuses["q1"] == EvalItemStatus.HIT
    assert statuses["q2"] == EvalItemStatus.INVALID

    hit = next(item for item in page.items if item.question_id == "q1")
    assert hit.relocated is True
    assert hit.best_rank == 1
    assert hit.recall["recall@10"] is True
