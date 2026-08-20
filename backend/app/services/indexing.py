"""入库管线：解析结果 → 分块 → 向量化 → 写索引与元数据。"""

from uuid import UUID

from app.core.exceptions import NotImplementedStageError
from app.repositories.base import ChunkRepository
from app.services.chunking import Chunker
from app.services.embedding import EmbeddingService
from app.vector.base import VectorRepository


class IndexingPipeline:
    def __init__(
        self,
        chunker: Chunker,
        embeddings: EmbeddingService,
        vector: VectorRepository,
        chunks: ChunkRepository,
    ) -> None:
        self._chunker = chunker
        self._embeddings = embeddings
        self._vector = vector
        self._chunks = chunks

    async def run(self, markdown: str, *, document_id: UUID) -> None:
        """M1 落地。先清旧 chunks（幂等），再分块、向量化、写库与索引。"""
        raise NotImplementedStageError("M1: 入库管线")
