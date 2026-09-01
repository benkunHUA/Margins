"""文档分块：Markdown 结构感知切分（按字符近似 token，避免 tiktoken 在线下载）。"""

import html
import re
from abc import ABC, abstractmethod
from uuid import UUID

from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter

from app.domain.entities import Chunk

TABLE_RE = re.compile(r"<table.*?</table>", re.S)


def _tables_to_text(markdown: str) -> str:
    """把 HTML 表格转成文本行，避免分块把表格切碎。"""

    def convert(match: re.Match) -> str:
        block = match.group(0)
        lines: list[str] = []
        for row in re.findall(r"<tr.*?</tr>", block, re.S):
            cells = re.findall(r"<t[hd].*?>(.*?)</t[hd]>", row, re.S)
            cleaned = [
                html.unescape(re.sub(r"<[^>]+>", "", cell)).strip() for cell in cells
            ]
            if any(cleaned):
                lines.append(" | ".join(cleaned))
        return "\n".join(lines)

    return TABLE_RE.sub(convert, markdown)


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
        markdown = _tables_to_text(markdown)
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
