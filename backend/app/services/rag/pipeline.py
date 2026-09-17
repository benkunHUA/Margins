"""RAG 管线编排（事件流）。"""

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
from app.index.ports import RetrievalScope
from app.services.llm import ChatMessage, LLMClient
from app.services.rag.context_builder import ContextBuilder
from app.services.rag.hybrid_retriever import HybridRetriever
from app.services.rag.postprocess import (
    cap_per_document,
    filter_citations,
    merge_candidates,
)
from app.services.rag.query_rewriter import QueryRewriter
from app.services.rag.trace import Trace
from app.services.reranking import Reranker

logger = get_logger(__name__)


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
        trace: Trace | None = None,
        scope: RetrievalScope | None = None,
    ) -> AsyncIterator[RagEvent]:
        start = time.perf_counter()
        try:
            t0 = time.perf_counter()
            if trace is not None:
                queries = await self._rewriter.rewrite(question, history, trace=trace)
            else:
                queries = await self._rewriter.rewrite(question, history)
            rewrite_ms = round((time.perf_counter() - t0) * 1000, 1)
            t0 = time.perf_counter()
            result_lists = []
            for query in queries:
                if trace is not None:
                    result_lists.append(
                        await self._hybrid.retrieve(query, scope=scope, trace=trace)
                    )
                else:
                    result_lists.append(await self._hybrid.retrieve(query, scope=scope))
            candidates = merge_candidates(result_lists)
            retrieve_ms = round((time.perf_counter() - t0) * 1000, 1)
            t0 = time.perf_counter()
            reranked = await self._reranker.rerank(
                question,
                candidates,
                top_n=self._config.rerank_top_n,
                threshold=self._config.relevance_threshold,
            )
            rerank_ms = round((time.perf_counter() - t0) * 1000, 1)
            if trace is not None:
                trace.record(
                    stage="rerank",
                    label="重排序",
                    duration_ms=rerank_ms,
                    summary=f"{len(candidates)} 候选 → {len(reranked)} 条",
                    data={
                        "candidates": len(candidates),
                        "top_n": self._config.rerank_top_n,
                        "threshold": self._config.relevance_threshold,
                        "returned": len(reranked),
                        "results": [
                            {
                                "chunk_id": str(item.chunk.id),
                                "doc_title": item.chunk.metadata.get("doc_title"),
                                "score": round(item.score, 4),
                                "snippet": item.chunk.content[:120],
                            }
                            for item in reranked[:10]
                        ],
                    },
                )
            capped = cap_per_document(reranked, self._config.max_chunks_per_document)
            capped = [
                item
                for item in capped
                if len(item.chunk.content.strip()) >= self._config.min_chunk_chars
            ]
            top = capped[: self._config.rerank_top_n]
            bundle = self._context_builder.build(
                top,
                history,
                question,
            )
            messages = [ChatMessage(**item) for item in bundle.messages]
            if trace is not None:
                trace.record(
                    stage="context",
                    label="上下文与 Prompt",
                    duration_ms=0,
                    summary=f"引用 {len(bundle.citations)} 条",
                    data={
                        "top_k": len(top),
                        "reference_count": len(bundle.citations),
                        "history_limit": self._config.history_limit,
                        "references": [
                            {
                                "index": index,
                                "doc_title": citation.doc_title,
                                "heading_path": citation.heading_path,
                                "snippet": citation.snippet,
                            }
                            for index, citation in enumerate(bundle.citations, start=1)
                        ],
                        "prompt": {
                            "messages": [
                                {"role": m.role, "content": m.content} for m in messages
                            ]
                        },
                    },
                )
            logger.info(
                "Prompt 内容",
                extra={
                    "extra_fields": {
                        "event": "prompt",
                        "messages": [
                            {"role": message.role, "content": message.content}
                            for message in messages
                        ],
                    }
                },
            )
            parts: list[str] = []
            t0 = time.perf_counter()
            stream_chunks = 0
            async for delta in self._llm_client.stream(messages):
                parts.append(delta)
                stream_chunks += 1
                yield DeltaEvent(content=delta)
            llm_ms = round((time.perf_counter() - t0) * 1000, 1)
            answer = "".join(parts)
            if trace is not None:
                trace.record(
                    stage="llm",
                    label="LLM 生成",
                    duration_ms=llm_ms,
                    summary=f"{stream_chunks} 个流式块 · {len(answer)} 字",
                    data={
                        "stream_chunks": stream_chunks,
                        "duration_ms": llm_ms,
                        "answer_excerpt": answer[:200],
                        "output_tokens_estimate": len(answer) // 2,
                    },
                )
            citations = filter_citations(
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
