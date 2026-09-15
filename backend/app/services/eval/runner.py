"""评估执行器：FastAPI 进程内 asyncio 后台跑批，进度与明细写库。"""

import asyncio
import time
from datetime import UTC, datetime
from uuid import UUID

from app.core.config import RetrievalConfig, RewriteConfig, Settings
from app.core.logging import get_logger
from app.domain.entities import Chunk, EvalRun, EvalRunConfig, EvalRunItem
from app.domain.enums import EvalItemStatus, EvalRunStatus
from app.repositories.base import (
    ChunkRepository,
    DocumentRepository,
    EvalDatasetRepository,
    EvalRunItemRepository,
    EvalRunRepository,
)
from app.services.embedding import EmbeddingService
from app.services.eval.gold_resolver import resolve_item_gold
from app.services.eval.metrics import (
    aggregate_metrics,
    citation_stats,
    first_hit_rank,
    is_refusal,
    ndcg_at_k,
    point_coverage,
    recall_flags,
)
from app.services.llm import ChatMessage, LLMClient
from app.services.rag.context_builder import ContextBuilder
from app.services.rag.hybrid_retriever import HybridRetriever
from app.services.rag.postprocess import (
    cap_per_document,
    filter_citations,
    merge_candidates,
)
from app.services.rag.query_rewriter import LLMQueryRewriter
from app.services.reranking import DashScopeReranker, Reranker
from app.vector.base import SparseIndex, VectorRepository
from app.vector.fusion import RRFFusion

logger = get_logger(__name__)


class EvalRunner:
    def __init__(
        self,
        *,
        datasets: EvalDatasetRepository,
        runs: EvalRunRepository,
        items: EvalRunItemRepository,
        documents: DocumentRepository,
        chunks: ChunkRepository,
        embeddings: EmbeddingService,
        vector: VectorRepository,
        sparse: SparseIndex,
        fusion: RRFFusion,
        reranker: Reranker,
        llm_client: LLMClient,
        settings: Settings,
    ) -> None:
        self._datasets = datasets
        self._runs = runs
        self._items = items
        self._documents = documents
        self._chunks = chunks
        self._embeddings = embeddings
        self._vector = vector
        self._sparse = sparse
        self._fusion = fusion
        self._reranker = reranker
        self._llm = llm_client
        self._settings = settings
        self._task: asyncio.Task | None = None

    async def start(self, run_id: UUID) -> None:
        if self._task is not None and not self._task.done():
            raise RuntimeError("已有评估任务在运行")
        self._task = asyncio.create_task(self._execute(run_id))

    async def run(self, run_id: UUID) -> None:
        """同步执行（CLI 用），与 start 共享同一执行逻辑。"""
        await self._execute(run_id)

    async def shutdown(self) -> None:
        if self._task is not None and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        await self._runs.mark_active_failed("服务重启中断")

    async def _execute(self, run_id: UUID) -> None:
        run = await self._runs.get(run_id)
        if run is None:
            return
        dataset = await self._datasets.get(run.dataset_id)
        if dataset is None:
            run.status = EvalRunStatus.FAILED
            run.error = "数据集不存在"
            await self._runs.update(run)
            return
        run.status = EvalRunStatus.RUNNING
        run.started_at = datetime.now(UTC)
        await self._runs.update(run)
        try:
            documents = await self._documents.list_all()
            title_by_doc_id = {str(doc.id): doc.filename for doc in documents}
            chunks = await self._chunks.list_all()
            chunk_by_id = {str(chunk.id): chunk for chunk in chunks}
            doc_title_by_chunk = {
                str(chunk.id): title_by_doc_id.get(str(chunk.document_id))
                or chunk.metadata.get("doc_title", "")
                for chunk in chunks
            }
            chunks_by_doc_title: dict[str, list[Chunk]] = {}
            for chunk in chunks:
                title = title_by_doc_id.get(str(chunk.document_id))
                if title:
                    chunks_by_doc_title.setdefault(title, []).append(chunk)

            resolutions = {
                item.id: resolve_item_gold(item, chunks_by_doc_title=chunks_by_doc_title)
                for item in dataset.payload.items
            }
            run.progress_total = len(dataset.payload.items) * max(len(run.configs), 1)
            await self._runs.update(run)

            rewrite_cache: dict[tuple[str, bool], list[str]] = {}
            per_config_rows: dict[str, list[dict]] = {
                str(index): [] for index in range(len(run.configs))
            }
            config_counts: dict[str, dict[str, int]] = {
                str(index): {"invalid": 0, "no_answer": 0, "error": 0}
                for index in range(len(run.configs))
            }
            for config_index, config in enumerate(run.configs):
                retrieval_config, rewriter, hybrid, reranker, context_builder = (
                    self._build_components(config)
                )
                for item in dataset.payload.items:
                    row = await self._evaluate_item(
                        run=run,
                        config_index=config_index,
                        item=item,
                        resolution=resolutions[item.id],
                        rewriter=rewriter,
                        hybrid=hybrid,
                        reranker=reranker,
                        context_builder=context_builder,
                        retrieval_config=retrieval_config,
                        rewrite_cache=rewrite_cache,
                        rewrite_enabled=config.rewrite_enabled,
                        chunk_by_id=chunk_by_id,
                        doc_title_by_chunk=doc_title_by_chunk,
                    )
                    await self._items.add_many([row])
                    if row.item_status not in (
                        EvalItemStatus.NO_ANSWER,
                        EvalItemStatus.INVALID,
                        EvalItemStatus.ERROR,
                    ):
                        per_config_rows[str(config_index)].append(
                            {
                                **row.recall,
                                "mrr": (1 / row.best_rank) if row.best_rank else 0.0,
                                "ndcg@10": row.ndcg or 0.0,
                                "hit": row.item_status == EvalItemStatus.HIT,
                                "durations": row.durations,
                            }
                        )
                    counts = config_counts[str(config_index)]
                    if row.item_status == EvalItemStatus.INVALID:
                        counts["invalid"] += 1
                    elif row.item_status == EvalItemStatus.NO_ANSWER:
                        counts["no_answer"] += 1
                    elif row.item_status == EvalItemStatus.ERROR:
                        counts["error"] += 1
                    run.progress_done += 1
                    await self._runs.update(run)
                run.metrics[str(config_index)] = {
                    **aggregate_metrics(per_config_rows[str(config_index)]),
                    **config_counts[str(config_index)],
                }
                await self._runs.update(run)
            run.status = EvalRunStatus.SUCCEEDED
        except Exception as exc:  # noqa: BLE001 - 汇总进 run.error
            logger.exception("评估任务失败: %s", run_id)
            run.status = EvalRunStatus.FAILED
            run.error = str(exc)
        finally:
            run.finished_at = datetime.now(UTC)
            await self._runs.update(run)

    def _build_components(self, config: EvalRunConfig):
        base = self._settings.retrieval
        retrieval_config = RetrievalConfig(
            recall_k=config.recall_k,
            rerank_top_n=config.rerank_top_n,
            relevance_threshold=config.relevance_threshold,
            max_citations=base.max_citations,
            max_chunks_per_document=base.max_chunks_per_document,
            min_chunk_chars=base.min_chunk_chars,
            history_limit=base.history_limit,
        )
        rewriter = LLMQueryRewriter(
            self._llm,
            RewriteConfig(
                enabled=config.rewrite_enabled,
                history_limit=self._settings.rewrite.history_limit,
                temperature=self._settings.rewrite.temperature,
            ),
        )
        hybrid = HybridRetriever(
            self._vector,
            self._sparse,
            self._embeddings,
            self._fusion,
            retrieval_config,
        )
        if config.rerank_model:
            model_config = self._settings.models.model_copy(
                update={"rerank_model": config.rerank_model}
            )
            reranker: Reranker = DashScopeReranker(model_config)
        else:
            reranker = self._reranker
        return (
            retrieval_config,
            rewriter,
            hybrid,
            reranker,
            ContextBuilder(retrieval_config),
        )

    async def _evaluate_item(
        self,
        *,
        run: EvalRun,
        config_index: int,
        item,
        resolution,
        rewriter,
        hybrid,
        reranker,
        context_builder,
        retrieval_config: RetrievalConfig,
        rewrite_cache: dict[tuple[str, bool], list[str]],
        rewrite_enabled: bool,
        chunk_by_id: dict[str, Chunk],
        doc_title_by_chunk: dict[str, str],
    ) -> EvalRunItem:
        started = time.perf_counter()
        base = dict(
            run_id=run.id,
            config_index=config_index,
            question_id=item.id,
            question=item.question,
            category=item.category,
            resolution_source=resolution.source,
            relocated=resolution.relocated,
        )
        if item.category == "no_answer":
            return EvalRunItem(**base, item_status=EvalItemStatus.NO_ANSWER)
        if resolution.invalid:
            return EvalRunItem(**base, item_status=EvalItemStatus.INVALID)

        gold_ids = {str(cid) for cid in resolution.chunk_ids}
        try:
            t0 = time.perf_counter()
            cache_key = (item.question, rewrite_enabled)
            if cache_key in rewrite_cache:
                queries = rewrite_cache[cache_key]
            else:
                queries = await rewriter.rewrite(item.question, [])
                rewrite_cache[cache_key] = queries
            rewrite_ms = round((time.perf_counter() - t0) * 1000, 1)

            t0 = time.perf_counter()
            diagnostics: dict[str, int] = {}
            result_lists = [
                await hybrid.retrieve(query, stats=diagnostics) for query in queries
            ]
            candidates = merge_candidates(result_lists)
            retrieve_ms = round((time.perf_counter() - t0) * 1000, 1)

            t0 = time.perf_counter()
            reranked = await reranker.rerank(
                item.question,
                candidates,
                top_n=retrieval_config.rerank_top_n,
                threshold=retrieval_config.relevance_threshold,
            )
            rerank_ms = round((time.perf_counter() - t0) * 1000, 1)

            ranked_ids = [str(scored.chunk.id) for scored in reranked]
            hit_rank = first_hit_rank(ranked_ids, gold_ids)
            retrieved = [
                {
                    "rank": index,
                    "chunk_id": str(scored.chunk.id),
                    "doc_title": scored.chunk.metadata.get("doc_title"),
                    "heading_path": scored.chunk.heading_path,
                    "snippet": scored.chunk.content[:120],
                    "score": round(scored.score, 4),
                    "matched": str(scored.chunk.id) in gold_ids,
                }
                for index, scored in enumerate(
                    candidates[: retrieval_config.recall_k], start=1
                )
            ]
            row = EvalRunItem(
                **base,
                item_status=EvalItemStatus.HIT if hit_rank else EvalItemStatus.MISS,
                best_rank=hit_rank,
                recall=recall_flags(ranked_ids, gold_ids),
                ndcg=round(ndcg_at_k(ranked_ids, gold_ids), 4),
                retrieved=retrieved,
                gold_matched=[
                    {
                        "chunk_id": chunk_id,
                        "doc_title": doc_title_by_chunk.get(chunk_id, ""),
                        "heading_path": chunk_by_id[chunk_id].heading_path
                        if chunk_id in chunk_by_id
                        else None,
                        "snippet": chunk_by_id[chunk_id].content[:200]
                        if chunk_id in chunk_by_id
                        else "",
                    }
                    for chunk_id in sorted(gold_ids)
                ],
                durations={
                    "rewrite": rewrite_ms,
                    "retrieve": retrieve_ms,
                    "rerank": rerank_ms,
                    "total": round((time.perf_counter() - started) * 1000, 1),
                },
                diagnostics=diagnostics,
            )

            if run.mode.value == "full":
                capped = cap_per_document(
                    reranked, retrieval_config.max_chunks_per_document
                )
                top = [
                    item_
                    for item_ in capped
                    if len(item_.chunk.content) >= retrieval_config.min_chunk_chars
                ][: retrieval_config.rerank_top_n]
                bundle = context_builder.build(top, [], item.question)
                answer = await self._llm.complete(
                    [ChatMessage(**message) for message in bundle.messages]
                )
                citations = filter_citations(
                    bundle.citations, answer, retrieval_config.max_citations
                )
                cited_ids = [str(citation.chunk_id) for citation in citations]
                row.citations = citations
                row.durations["total"] = round((time.perf_counter() - started) * 1000, 1)
                row.recall = {**row.recall, **citation_stats(cited_ids, gold_ids)}
                row.recall["refusal"] = is_refusal(answer, citations)
                row.recall["points"] = point_coverage(
                    item.expected_answer_points, answer
                )
            return row
        except Exception as exc:  # noqa: BLE001 - 单题失败不中断
            return EvalRunItem(**base, item_status=EvalItemStatus.ERROR, error=str(exc))
