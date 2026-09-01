"""M2 检索管线测试（fake 向量/LLM；引用后置 + [n] 过滤 + 阈值）。"""

from uuid import uuid4

from app.core.config import RetrievalConfig
from app.domain.entities import Chunk, Message
from app.domain.enums import MessageRole
from app.domain.events import CitationsEvent, DeltaEvent, DoneEvent, ErrorEvent
from app.services.embedding import EmbeddingService
from app.services.llm import ChatMessage, LLMClient
from app.services.rag.context_builder import ContextBuilder
from app.services.rag.hybrid_retriever import HybridRetriever
from app.services.rag.pipeline import RAGPipeline
from app.vector.base import ScoredChunk, VectorRepository
from app.vector.fusion import RRFFusion


class EmptySparse:
    async def search(self, query, k):
        return []

    async def rebuild(self, chunks):
        pass


class FakeEmbeddings(EmbeddingService):
    async def embed_query(self, text: str):
        return [1.0, 0.0]

    async def embed_texts(self, texts):
        return [[1.0, 0.0]] * len(texts)


class FakeVector(VectorRepository):
    def __init__(self, chunks: list[Chunk], scores: list[float] | None = None) -> None:
        self.chunks = chunks
        self.scores = scores or [0.9 - index * 0.05 for index in range(len(chunks))]

    async def search(self, embedding, k):
        return [
            ScoredChunk(chunk=chunk, score=score)
            for chunk, score in zip(self.chunks, self.scores, strict=True)
        ]

    async def add(self, items):
        pass

    async def rebuild(self, chunks):
        pass

    async def save(self):
        pass

    async def load(self):
        pass


class FakeLLM(LLMClient):
    def __init__(self, tokens: list[str] | None = None) -> None:
        self.tokens = tokens or ["基于", "资料", "回答"]
        self.received: list[ChatMessage] = []

    async def stream(self, messages):
        self.received = list(messages)
        for token in self.tokens:
            yield token

    async def complete(self, messages):
        return ""


class FakeRewriter:
    def __init__(self, queries: list[str] | None = None) -> None:
        self.queries = queries or ["q"]

    async def rewrite(self, question, history):
        return self.queries


class FakeReranker:
    def __init__(self) -> None:
        self.calls = 0

    async def rerank(self, query, candidates, *, top_n, threshold):
        self.calls += 1
        return list(candidates)[:top_n]


def _chunk(title: str, content: str) -> Chunk:
    return Chunk(
        id=uuid4(),
        document_id=uuid4(),
        chunk_index=0,
        content=content,
        heading_path="第三章",
        metadata={"doc_title": title},
    )


def _config(**overrides) -> RetrievalConfig:
    defaults = dict(
        history_limit=6,
        relevance_threshold=0.3,
        max_citations=5,
        min_chunk_chars=0,
    )
    defaults.update(overrides)
    return RetrievalConfig(**defaults)


def _pipeline(
    chunks: list[Chunk],
    llm: FakeLLM | None = None,
    config: RetrievalConfig | None = None,
    rewriter: FakeRewriter | None = None,
    reranker: FakeReranker | None = None,
):
    cfg = config or _config()
    embeddings = FakeEmbeddings()
    hybrid = HybridRetriever(
        FakeVector(chunks), EmptySparse(), embeddings, RRFFusion(), cfg
    )
    llm = llm or FakeLLM()
    rag = RAGPipeline(
        rewriter=rewriter or FakeRewriter(),
        hybrid=hybrid,
        reranker=reranker or FakeReranker(),
        context_builder=ContextBuilder(cfg),
        llm_client=llm,
        config=cfg,
    )
    return rag, llm


async def test_pipeline_uses_rewrite_merge_and_rerank() -> None:
    chunks = [_chunk("a.pdf", "内容一"), _chunk("b.pdf", "内容二")]
    rewriter = FakeRewriter(queries=["q1", "q2"])
    reranker = FakeReranker()
    rag, _ = _pipeline(
        chunks,
        FakeLLM(tokens=["[1]", "回答"]),
        rewriter=rewriter,
        reranker=reranker,
    )
    events = [event async for event in rag.run("问题", [])]
    assert reranker.calls == 1
    assert any(isinstance(event, DeltaEvent) for event in events)
    assert isinstance(events[-1], DoneEvent)


async def test_pipeline_logs_summary(caplog) -> None:
    chunks = [_chunk("a.pdf", "内容一")]
    rag, _ = _pipeline(chunks, FakeLLM(tokens=["[1]", "回答"]))
    with caplog.at_level("INFO", logger="app.services.rag.pipeline"):
        events = [event async for event in rag.run("问题", [])]
    assert isinstance(events[-1], DoneEvent)
    assert any(
        getattr(record, "extra_fields", {}).get("event") == "rag_pipeline"
        for record in caplog.records
    )


async def test_pipeline_logs_prompt(caplog) -> None:
    chunks = [_chunk("a.pdf", "违约金条款内容")]
    rag, _ = _pipeline(chunks, FakeLLM(tokens=["[1]", "回答"]))
    with caplog.at_level("INFO", logger="app.services.rag.pipeline"):
        events = [event async for event in rag.run("违约金多少？", [])]
    assert isinstance(events[-1], DoneEvent)
    prompt_log = next(
        record
        for record in caplog.records
        if getattr(record, "extra_fields", {}).get("event") == "prompt"
    )
    messages = prompt_log.extra_fields["messages"]
    assert messages[0]["role"] == "system"
    content = messages[-1]["content"]
    assert "违约金多少？" in content
    assert "参考资料（共 1 条" in content
    assert "【引用 1】" in content


def test_cap_per_document_limits_each_document() -> None:
    doc_a = uuid4()
    doc_b = uuid4()
    items = [
        ScoredChunk(chunk=_chunk("a1", "内容一"), score=0.9),
        ScoredChunk(chunk=_chunk("a2", "内容二"), score=0.8),
        ScoredChunk(chunk=_chunk("b1", "内容三"), score=0.7),
    ]
    items[0].chunk.document_id = doc_a
    items[1].chunk.document_id = doc_a
    items[2].chunk.document_id = doc_b
    result = RAGPipeline._cap_per_document(items, cap=1)
    assert len(result) == 2
    assert {str(item.chunk.document_id) for item in result} == {str(doc_a), str(doc_b)}


async def test_pipeline_filters_short_chunks() -> None:
    chunks = [_chunk("a.pdf", "x")]
    rag, _ = _pipeline(
        chunks,
        FakeLLM(tokens=["[1]", "回答"]),
        config=_config(min_chunk_chars=30),
    )
    events = [event async for event in rag.run("q", [])]
    citations = next(
        event.citations for event in events if isinstance(event, CitationsEvent)
    )
    assert citations == []
    assert isinstance(events[-1], DoneEvent)


async def test_citations_arrive_after_deltas_with_only_referenced() -> None:
    chunks = [
        _chunk("a.pdf", "合同约定违约金为 10%。"),
        _chunk("b.pdf", "仲裁条款见第五章。"),
    ]
    rag, llm = _pipeline(chunks, FakeLLM(tokens=["根据", "[2]", "回答"]))
    history = [Message(session_id=uuid4(), role=MessageRole.USER, content="旧问题")]

    events = [event async for event in rag.run("违约金多少？", history)]

    delta_indexes = [i for i, e in enumerate(events) if isinstance(e, DeltaEvent)]
    citations_index = next(i for i, e in enumerate(events) if isinstance(e, CitationsEvent))
    assert delta_indexes and citations_index > delta_indexes[-1]  # 引用在回答之后
    assert isinstance(events[-1], DoneEvent)

    citations = events[citations_index].citations
    assert len(citations) == 1  # 只保留回答中引用的 [2]
    assert citations[0].doc_title == "b.pdf"
    assert llm.received[0].role == "system"
    assert "违约金" in llm.received[-1].content


async def test_citations_deduped_and_in_first_appearance_order() -> None:
    chunks = [
        _chunk("a.pdf", "内容一"),
        _chunk("b.pdf", "内容二"),
    ]
    rag, _ = _pipeline(chunks, FakeLLM(tokens=["[1]", "[2]", "[1]"]))

    events = [event async for event in rag.run("q", [])]
    citations = next(e.citations for e in events if isinstance(e, CitationsEvent))
    assert [c.doc_title for c in citations] == ["a.pdf", "b.pdf"]


async def test_citations_capped_by_config() -> None:
    chunks = [
        _chunk("a.pdf", "内容一"),
        _chunk("b.pdf", "内容二"),
    ]
    rag, _ = _pipeline(chunks, FakeLLM(tokens=["[1]", "[2]"]), _config(max_citations=1))

    events = [event async for event in rag.run("q", [])]
    citations = next(e.citations for e in events if isinstance(e, CitationsEvent))
    assert [c.doc_title for c in citations] == ["a.pdf"]


async def test_retrieval_threshold_filters_low_scores() -> None:
    chunks = [
        _chunk("a.pdf", "高相关"),
        _chunk("b.pdf", "低相关"),
    ]
    cfg = _config(relevance_threshold=0.3)
    hybrid = HybridRetriever(
        FakeVector(chunks, scores=[0.9, 0.1]),
        EmptySparse(),
        FakeEmbeddings(),
        RRFFusion(),
        cfg,
    )

    results = await hybrid.retrieve("q")
    assert [item.chunk.metadata["doc_title"] for item in results] == ["a.pdf"]


async def test_run_emits_error_on_failure() -> None:
    class BoomVector(FakeVector):
        async def search(self, embedding, k):
            raise RuntimeError("vector down")

    chunk = _chunk("a.pdf", "x")
    cfg = _config()
    hybrid = HybridRetriever(
        BoomVector([chunk]), EmptySparse(), FakeEmbeddings(), RRFFusion(), cfg
    )
    rag = RAGPipeline(
        rewriter=FakeRewriter(),
        hybrid=hybrid,
        reranker=FakeReranker(),
        context_builder=ContextBuilder(cfg),
        llm_client=FakeLLM(),
        config=cfg,
    )
    events = [event async for event in rag.run("q", [])]
    assert isinstance(events[-1], ErrorEvent)
