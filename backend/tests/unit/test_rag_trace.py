"""RAG 管线 Trace 埋点测试（全程 fake，验证各阶段被记录）。"""

from uuid import uuid4

from app.core.config import RetrievalConfig
from app.domain.entities import Chunk
from app.domain.events import DoneEvent
from app.index.fusion import RRFFusion
from app.services.embedding import EmbeddingService
from app.services.llm import LLMClient
from app.services.rag.context_builder import ContextBuilder
from app.services.rag.hybrid_retriever import HybridRetriever
from app.services.rag.pipeline import RAGPipeline
from app.services.rag.trace import Trace
from tests.index.fakes import StubIndexBackend


class FakeEmbeddings(EmbeddingService):
    async def embed_query(self, text: str):
        return [1.0, 0.0]

    async def embed_texts(self, texts):
        return [[1.0, 0.0]] * len(texts)


class FakeLLM(LLMClient):
    async def stream(self, messages):
        for token in ["基于", "资料", "回答"]:
            yield token

    async def complete(self, messages):
        return ""


def _chunk(title: str, content: str) -> Chunk:
    return Chunk(
        id=uuid4(),
        document_id=uuid4(),
        chunk_index=0,
        content=content,
        heading_path="第三章",
        metadata={"doc_title": title},
    )


class _Rewriter:
    async def rewrite(self, question, history, *, trace=None):
        if trace is not None:
            trace.record(
                stage="rewrite",
                label="查询改写",
                duration_ms=10,
                summary="需要改写",
                data={"queries": ["改写后"]},
            )
        return ["改写后"]


class _Reranker:
    async def rerank(self, query, candidates, *, top_n, threshold, trace=None):
        if trace is not None:
            trace.record(
                stage="rerank",
                label="重排序",
                duration_ms=10,
                summary="1 条",
                data={
                    "candidates": len(candidates),
                    "returned": min(len(candidates), top_n),
                },
            )
        return list(candidates)[:top_n]


async def test_pipeline_records_all_five_stages_into_trace() -> None:
    cfg = RetrievalConfig(
        history_limit=6,
        relevance_threshold=0.0,
        min_chunk_chars=0,
        recall_k=10,
        rerank_top_n=6,
    )
    embeddings = FakeEmbeddings()
    hybrid = HybridRetriever(
        StubIndexBackend([_chunk("a.pdf", "内容一")]),
        embeddings,
        RRFFusion(),
        cfg,
    )
    rag = RAGPipeline(
        rewriter=_Rewriter(),
        hybrid=hybrid,
        reranker=_Reranker(),
        context_builder=ContextBuilder(cfg),
        llm_client=FakeLLM(),
        config=cfg,
    )
    trace = Trace(session_id=uuid4(), session_title="会话", question="问题")

    events = [event async for event in rag.run("问题", [], trace=trace)]

    assert isinstance(events[-1], DoneEvent)
    stages = [step.stage for step in trace.steps()]
    assert stages == ["rewrite", "hybrid", "rerank", "context", "llm"]
    assert trace.steps()[0].data["queries"] == ["改写后"]
    assert trace.steps()[1].data["fused"] == 1
    assert trace.steps()[2].data["returned"] == 1
    assert trace.steps()[3].data["prompt"]["messages"][0]["role"] == "system"
    assert trace.steps()[4].data["stream_chunks"] == 3
