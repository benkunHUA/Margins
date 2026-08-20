"""RAG 管线编排（事件流）。"""

from collections.abc import AsyncIterator, Sequence

from app.core.config import RetrievalConfig
from app.domain.entities import Message
from app.domain.events import ErrorEvent, RagEvent
from app.services.llm import LLMClient
from app.services.rag.context_builder import ContextBuilder
from app.services.rag.hybrid_retriever import HybridRetriever
from app.services.rag.query_rewriter import QueryRewriter
from app.services.reranking import Reranker


class RAGPipeline:
    def __init__(
        self,
        rewriter: QueryRewriter,
        hybrid: HybridRetriever,
        reranker: Reranker,
        context_builder: ContextBuilder,
        llm_client: LLMClient,
        config: RetrievalConfig,
    ) -> None:
        self._rewriter = rewriter
        self._hybrid = hybrid
        self._reranker = reranker
        self._context_builder = context_builder
        self._llm_client = llm_client
        self._config = config

    async def run(
        self,
        question: str,
        history: Sequence[Message],
        *,
        final_k: int | None = None,
    ) -> AsyncIterator[RagEvent]:
        """M2/M3 落地：改写 → 混合检索 → 重排 → 组装 → 流式生成。"""
        yield ErrorEvent(code="NOT_IMPLEMENTED", message="检索管线将在 M2/M3 里程碑实现")
