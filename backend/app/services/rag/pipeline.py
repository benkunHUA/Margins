"""RAG 管线编排（事件流）。"""

from collections.abc import AsyncIterator, Sequence

from app.core.config import RetrievalConfig
from app.domain.entities import Message
from app.domain.events import (
    CitationsEvent,
    DeltaEvent,
    DoneEvent,
    ErrorEvent,
    RagEvent,
)
from app.services.llm import ChatMessage, LLMClient
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
        try:
            candidates = await self._hybrid.retrieve(question)
            top = candidates[: final_k or self._config.final_k]
            bundle = self._context_builder.build(
                top,
                history,
                question,
                token_budget=self._config.context_token_budget,
            )
            yield CitationsEvent(citations=bundle.citations)
            messages = [ChatMessage(**item) for item in bundle.messages]
            async for delta in self._llm_client.stream(messages):
                yield DeltaEvent(content=delta)
        except Exception as exc:
            yield ErrorEvent(code="RAG_ERROR", message=str(exc))
            return
        yield DoneEvent(message_id="")
