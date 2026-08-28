"""RAG 管线编排（事件流）。"""

import re
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

CITATION_MARKER = re.compile(r"\[(\d{1,2})\]")


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
            messages = [ChatMessage(**item) for item in bundle.messages]
            parts: list[str] = []
            async for delta in self._llm_client.stream(messages):
                parts.append(delta)
                yield DeltaEvent(content=delta)
            answer = "".join(parts)
            citations = self._filter_citations(
                bundle.citations,
                answer,
                self._config.max_citations,
            )
            yield CitationsEvent(citations=citations)
        except Exception as exc:
            yield ErrorEvent(code="RAG_ERROR", message=str(exc))
            return
        yield DoneEvent(message_id="")

    @staticmethod
    def _filter_citations(citations, answer: str, cap: int) -> list:
        """只保留回答中实际引用的 [n]，按首次出现顺序去重并截断。"""
        picked: list[int] = []
        for marker in CITATION_MARKER.findall(answer):
            index = int(marker)
            if 1 <= index <= len(citations) and index - 1 not in picked:
                picked.append(index - 1)
                if len(picked) >= cap:
                    break
        return [citations[i] for i in picked]
