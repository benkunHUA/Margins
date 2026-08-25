"""入库管线：解析结果 → 分块 → 向量化 → 写索引与元数据。"""

from uuid import UUID

from app.core.exceptions import ParseFailedError
from app.repositories.base import ChunkRepository
from app.services.chunking import Chunker
from app.services.embedding import EmbeddingService
from app.vector.base import IndexableChunk, VectorRepository


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
        await self._chunks.delete_by_document(document_id)  # 幂等：先清旧块
        chunks = self._chunker.chunk(markdown, document_id=document_id)
        if not chunks:
            raise ParseFailedError("解析结果为空，无法入库")

        texts = [chunk.content for chunk in chunks]
        embeddings = await self._embeddings.embed_texts(texts)

        await self._chunks.add_many(chunks)
        await self._vector.add(
            [
                IndexableChunk(chunk=chunk, embedding=embedding)
                for chunk, embedding in zip(chunks, embeddings, strict=True)
            ]
        )
