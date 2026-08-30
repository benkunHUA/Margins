"""RAG 管线编排（事件流）。"""

import re
import time
from collections.abc import AsyncIterator, Sequence

from app.core.config import RetrievalConfig
from app.core.logging import get_logger
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
from app.vector.base import ScoredChunk

logger = get_logger(__name__)

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
        start = time.perf_counter()
        try:
            t0 = time.perf_counter()
            queries = await self._rewriter.rewrite(question, history)
            rewrite_ms = round((time.perf_counter() - t0) * 1000, 1)
            t0 = time.perf_counter()
            merged: dict[str, ScoredChunk] = {}
            for query in queries:
                for item in await self._hybrid.retrieve(query):
                    key = str(item.chunk.id)
                    if key not in merged or item.score > merged[key].score:
                        merged[key] = item
            candidates = list(merged.values())
            retrieve_ms = round((time.perf_counter() - t0) * 1000, 1)
            t0 = time.perf_counter()
            reranked = await self._reranker.rerank(
                question,
                candidates,
                top_n=self._config.rerank_top_n,
                threshold=self._config.relevance_threshold,
            )
            rerank_ms = round((time.perf_counter() - t0) * 1000, 1)
            top = reranked[: final_k or self._config.final_k]
            bundle = self._context_builder.build(
                top,
                history,
                question,
                token_budget=self._config.context_token_budget,
            )
            messages = [ChatMessage(**item) for item in bundle.messages]
            parts: list[str] = []
            t0 = time.perf_counter()
            async for delta in self._llm_client.stream(messages):
                parts.append(delta)
                yield DeltaEvent(content=delta)
            llm_ms = round((time.perf_counter() - t0) * 1000, 1)
            answer = "".join(parts)
            citations = self._filter_citations(
                bundle.citations,
                answer,
                self._config.max_citations,
            )
            yield CitationsEvent(citations=citations)
            logger.info(
                "RAG 管线完成",
                extra={
                    "extra_fields": {
                        "event": "rag_pipeline",
                        "queries": queries,
                        "merged_candidates": len(candidates),
                        "reranked": len(reranked),
                        "top_k": len(top),
                        "citations": len(citations),
                        "rewrite_ms": rewrite_ms,
                        "retrieve_ms": retrieve_ms,
                        "rerank_ms": rerank_ms,
                        "llm_ms": llm_ms,
                        "total_ms": round((time.perf_counter() - start) * 1000, 1),
                    }
                },
            )
        except Exception as exc:
            logger.exception(
                "RAG 管线异常",
                extra={"extra_fields": {"event": "rag_pipeline_error", "error": str(exc)}},
            )
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
