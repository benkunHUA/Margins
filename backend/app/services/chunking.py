"""文档分块：Markdown 结构感知切分（按字符近似 token，避免 tiktoken 在线下载）。"""

from abc import ABC, abstractmethod
from uuid import UUID

from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter

from app.domain.entities import Chunk


class Chunker(ABC):
    @abstractmethod
    def chunk(self, markdown: str, *, document_id: UUID) -> list[Chunk]: ...


class MarkdownChunker(Chunker):
    """按 H1-H3 保留章节路径，再按字符长度二次切分。

    中文约 1 字 ≈ 0.6-0.7 token，chunk_token_size=600 时取 1200 字符。
    """

    def __init__(self, chunk_token_size: int = 600, overlap: int = 80) -> None:
        self._header_splitter = MarkdownHeaderTextSplitter(
            headers_to_split_on=[("#", "h1"), ("##", "h2"), ("###", "h3")],
            strip_headers=False,
        )
        self._text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_token_size * 2,
            chunk_overlap=overlap * 2,
            separators=["\n\n", "\n", "。", "；", "，", " ", ""],
        )

    def chunk(self, markdown: str, *, document_id: UUID) -> list[Chunk]:
        if not markdown.strip():
            return []

        chunks: list[Chunk] = []
        index = 0
        for section in self._header_splitter.split_text(markdown):
            heading_path = " / ".join(str(v) for v in section.metadata.values()) or None
            for piece in self._text_splitter.split_text(section.page_content):
                chunks.append(
                    Chunk(
                        document_id=document_id,
                        chunk_index=index,
                        content=piece,
                        heading_path=heading_path,
                        token_count=max(1, len(piece) // 2),
                    )
                )
                index += 1
        return chunks
