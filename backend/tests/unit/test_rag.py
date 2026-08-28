"""M2 检索管线测试（fake 向量/LLM）。"""

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


class FakeEmbeddings(EmbeddingService):
    async def embed_query(self, text: str):
        return [1.0, 0.0]

    async def embed_texts(self, texts):
        return [[1.0, 0.0]] * len(texts)


class FakeVector(VectorRepository):
    def __init__(self, chunk: Chunk) -> None:
        self.chunk = chunk

    async def search(self, embedding, k):
        return [ScoredChunk(chunk=self.chunk, score=0.9)]

    async def add(self, items):
        pass

    async def rebuild(self, chunks):
        pass

    async def save(self):
        pass

    async def load(self):
        pass


class FakeLLM(LLMClient):
    def __init__(self) -> None:
        self.received: list[ChatMessage] = []

    async def stream(self, messages):
        self.received = list(messages)
        for token in ["基于", "资料", "回答"]:
            yield token


def _config() -> RetrievalConfig:
    return RetrievalConfig(
        dense_k=30,
        final_k=3,
        history_limit=6,
        context_token_budget=12000,
    )


def _pipeline(chunk: Chunk):
    embeddings = FakeEmbeddings()
    vector = FakeVector(chunk)
    sparse = type("Sparse", (), {})()
    hybrid = HybridRetriever(vector, sparse, embeddings, None, _config())
    llm = FakeLLM()
    rag = RAGPipeline(
        rewriter=type("Rewriter", (), {})(),
        hybrid=hybrid,
        reranker=type("Reranker", (), {})(),
        context_builder=ContextBuilder(_config()),
        llm_client=llm,
        config=_config(),
    )
    return rag, llm


async def test_run_emits_citations_delta_done() -> None:
    chunk = Chunk(
        id=uuid4(),
        document_id=uuid4(),
        chunk_index=0,
        content="合同约定违约金为 10%。",
        heading_path="第三章",
        metadata={"doc_title": "合同.pdf"},
    )
    rag, llm = _pipeline(chunk)
    history = [Message(session_id=uuid4(), role=MessageRole.USER, content="旧问题")]

    events = [event async for event in rag.run("违约金多少？", history)]
    assert isinstance(events[0], CitationsEvent)
    assert events[0].citations[0].doc_title == "合同.pdf"
    assert any(isinstance(e, DeltaEvent) for e in events)
    assert isinstance(events[-1], DoneEvent)
    assert llm.received[0].role == "system"
    assert "违约金" in llm.received[-1].content


async def test_run_emits_error_on_failure() -> None:
    class BoomVector(FakeVector):
        async def search(self, embedding, k):
            raise RuntimeError("vector down")

    chunk = Chunk(id=uuid4(), document_id=uuid4(), chunk_index=0, content="x")
    embeddings = FakeEmbeddings()
    hybrid = HybridRetriever(
        BoomVector(chunk), type("Sparse", (), {})(), embeddings, None, _config()
    )
    rag = RAGPipeline(
        rewriter=type("Rewriter", (), {})(),
        hybrid=hybrid,
        reranker=type("Reranker", (), {})(),
        context_builder=ContextBuilder(_config()),
        llm_client=FakeLLM(),
        config=_config(),
    )
    events = [event async for event in rag.run("q", [])]
    assert isinstance(events[-1], ErrorEvent)
