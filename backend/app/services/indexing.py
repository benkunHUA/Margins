"""入库管线：解析结果 → 分块 → 交给 IndexWriter 原子写索引。

这一层只做"分块 + 编排"：向量化与三表写入都在 `IndexWriter`，
避免再出现"M1 写元数据、M3 重建内存索引"那种多步不一致状态。
"""

from uuid import UUID

from app.core.exceptions import ParseFailedError
from app.index.writer import IndexWriter
from app.services.chunking import Chunker


class IndexingPipeline:
    def __init__(self, chunker: Chunker, writer: IndexWriter) -> None:
        self._chunker = chunker
        self._writer = writer

    async def run(
        self,
        markdown: str,
        *,
        document_id: UUID,
        doc_title: str | None = None,
    ) -> None:
        chunks = self._chunker.chunk(markdown, document_id=document_id)
        if not chunks:
            raise ParseFailedError("解析结果为空，无法入库")
        await self._writer.write(
            document_id=document_id,
            chunks=chunks,
            doc_title=doc_title,
        )
