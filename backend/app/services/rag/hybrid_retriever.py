"""混合检索：Faiss 稠密 + BM25 稀疏 + RRF 融合。"""

from app.core.config import RetrievalConfig
from app.core.exceptions import NotImplementedStageError
from app.services.embedding import EmbeddingService
from app.vector.base import SparseIndex, VectorRepository
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

    async def retrieve(self, query: str):
        """M3 落地：dense(sparse_k) + sparse(sparse_k) → RRF → top fusion_top_n。"""
        raise NotImplementedStageError("M3: 混合检索")
