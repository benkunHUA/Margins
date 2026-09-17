"""混合检索：向量路 + 关键词路 → RRF 融合。

只依赖 `IndexBackendPort`：具体是 Faiss / BM25 还是 SQLite FTS5 + vec0 由容器决定。
`RetrievalScope` 直接下推给索引层（SQL 过滤），不在应用层做全量扫描。
"""

import time

from app.core.config import RetrievalConfig
from app.core.logging import get_logger
from app.index.fusion import RRFFusion
from app.index.ports import IndexBackendPort, RetrievalScope
from app.index.values import ScoredChunk
from app.services.embedding import EmbeddingService

logger = get_logger(__name__)

RRF_K = 60


class HybridRetriever:
    def __init__(
        self,
        backend: IndexBackendPort,
        embeddings: EmbeddingService,
        fusion: RRFFusion,
        config: RetrievalConfig,
    ) -> None:
        self._backend = backend
        self._embeddings = embeddings
        self._fusion = fusion
        self._config = config

    async def retrieve(
        self,
        query: str,
        *,
        scope: RetrievalScope | None = None,
        trace=None,
        stats: dict | None = None,
    ) -> list[ScoredChunk]:
        start = time.perf_counter()
        embedding = await self._embeddings.embed_query(query)
        dense_raw = await self._backend.dense.search(embedding, self._config.recall_k, scope)
        threshold = self._config.relevance_threshold
        dense = dense_raw
        if threshold > 0:
            dense = [item for item in dense_raw if item.score >= threshold]
        sparse = await self._backend.sparse.search(query, self._config.recall_k, scope)
        fused = self._fusion.fuse(
            [dense, sparse],
            k=RRF_K,
            top_n=self._config.recall_k,
        )
        scope_ids = [str(document_id) for document_id in (scope.document_ids if scope else ())]
        if stats is not None:
            for key, value in {
                "dense_raw": len(dense_raw),
                "dense_filtered": len(dense),
                "sparse": len(sparse),
                "fused": len(fused),
            }.items():
                stats[key] = stats.get(key, 0) + value
        logger.info(
            "混合检索完成",
            extra={
                "extra_fields": {
                    "event": "hybrid",
                    "query": query,
                    "scope": scope_ids,
                    "dense_raw": len(dense_raw),
                    "dense_filtered": len(dense),
                    "sparse": len(sparse),
                    "fused": len(fused),
                    "results": [
                        {
                            "chunk_id": str(item.chunk.id),
                            "doc_title": item.chunk.metadata.get("doc_title"),
                            "score": round(item.score, 4),
                        }
                        for item in fused[:10]
                    ],
                    "duration_ms": round((time.perf_counter() - start) * 1000, 1),
                }
            },
        )
        if trace is not None:
            trace.record(
                stage="hybrid",
                label="混合检索",
                duration_ms=round((time.perf_counter() - start) * 1000, 1),
                summary=f"稠密 {len(dense)} + 稀疏 {len(sparse)} → 融合 {len(fused)}",
                data={
                    "query": query,
                    "scope": scope_ids,
                    "dense_raw": len(dense_raw),
                    "dense_filtered": len(dense),
                    "sparse": len(sparse),
                    "fused": len(fused),
                    "top_results": [
                        {
                            "chunk_id": str(item.chunk.id),
                            "doc_title": item.chunk.metadata.get("doc_title"),
                            "score": round(item.score, 4),
                            "snippet": item.chunk.content[:120],
                        }
                        for item in fused[:10]
                    ],
                },
            )
        return fused
