"""索引写入器：embedding 在事务外完成，随后一次性 apply 写入三张表。"""

from collections.abc import Sequence
from uuid import UUID

from app.domain.entities import Chunk
from app.index.ports import IndexBackendPort, IndexChangeSet, IndexRecord
from app.services.embedding import EmbeddingService


class IndexWriter:
    """入库的唯一写入入口：先按文档删旧（幂等重解析），再写入新块。"""

    def __init__(self, backend: IndexBackendPort, embeddings: EmbeddingService) -> None:
        self._backend = backend
        self._embeddings = embeddings

    async def write(
        self,
        *,
        document_id: UUID,
        chunks: Sequence[Chunk],
        doc_title: str | None = None,
    ) -> None:
        embeddings = await self._embeddings.embed_texts([chunk.content for chunk in chunks])
        records = [
            IndexRecord(
                chunk_id=chunk.id,
                document_id=document_id,
                content=chunk.content,
                embedding=embedding,
                chunk_index=chunk.chunk_index,
                heading_path=chunk.heading_path,
                page=chunk.page,
                token_count=chunk.token_count,
                metadata=_metadata(chunk, doc_title),
            )
            for chunk, embedding in zip(chunks, embeddings, strict=True)
        ]
        await self._backend.apply(
            IndexChangeSet(delete_documents=[document_id], upserts=records)
        )

    async def delete_document(self, document_id: UUID) -> None:
        await self._backend.apply(IndexChangeSet(delete_documents=[document_id]))


def _metadata(chunk: Chunk, doc_title: str | None) -> dict:
    metadata = dict(chunk.metadata)
    if doc_title:
        metadata["doc_title"] = doc_title
    return metadata
