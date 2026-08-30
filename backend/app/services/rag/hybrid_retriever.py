"""混合检索：M2 走 Faiss 稠密路；M3 增加 BM25 稀疏 + RRF 融合。"""

from app.core.config import RetrievalConfig
from app.services.embedding import EmbeddingService
from app.vector.base import ScoredChunk, SparseIndex, VectorRepository
from app.vector.fusion import RRFFusion


class HybridRetriever:
    def __init__(
        self,
        vector: VectorRepository,
        sparse: SparseIndex,
        embeddings: EmbeddingService,
        fusion: RRFFusion,
        config: RetrievalConfig,
    ) -> None:
        self._vector = vector
        self._sparse = sparse
        self._embeddings = embeddings
        self._fusion = fusion
        self._config = config

    async def retrieve(self, query: str) -> list[ScoredChunk]:
        embedding = await self._embeddings.embed_query(query)
        dense = await self._vector.search(embedding, self._config.dense_k)
        threshold = self._config.relevance_threshold
        if threshold > 0:
            dense = [item for item in dense if item.score >= threshold]
        sparse = await self._sparse.search(query, self._config.sparse_k)
        return self._fusion.fuse(
            [dense, sparse],
            k=self._config.rrf_k,
            top_n=self._config.fusion_top_n,
        )
