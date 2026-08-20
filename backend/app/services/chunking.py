"""文档分块：Markdown 结构感知切分。"""

from abc import ABC, abstractmethod
from uuid import UUID

from app.core.exceptions import NotImplementedStageError
from app.domain.entities import Chunk


class Chunker(ABC):
    @abstractmethod
    def chunk(self, markdown: str, *, document_id: UUID) -> list[Chunk]: ...


class MarkdownChunker(Chunker):
    """M1 落地：MarkdownHeaderTextSplitter + RecursiveCharacterTextSplitter。"""

    def chunk(self, markdown: str, *, document_id: UUID) -> list[Chunk]:
        raise NotImplementedStageError("M1: 结构分块")
