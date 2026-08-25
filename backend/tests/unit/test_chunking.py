"""Markdown 结构分块测试。"""

from uuid import uuid4

from app.services.chunking import MarkdownChunker


def _chunker() -> MarkdownChunker:
    return MarkdownChunker(chunk_token_size=600, overlap=80)


def test_headers_are_kept_in_heading_path() -> None:
    markdown = "# 第一章\n\n## 1.1 环境\n\n正文内容 A\n\n## 1.2 安装\n\n正文内容 B\n"
    chunks = _chunker().chunk(markdown, document_id=uuid4())
    headings = {chunk.heading_path for chunk in chunks}
    assert any("第一章" in (h or "") for h in headings)
    assert any("1.1 环境" in (h or "") for h in headings)
    assert any("1.2 安装" in (h or "") for h in headings)
    assert all(chunk.content.strip() for chunk in chunks)


def test_long_text_is_split_into_multiple_chunks() -> None:
    body = "这是用于测试分块的长文本。" * 300
    chunks = _chunker().chunk(f"# 标题\n\n{body}", document_id=uuid4())
    assert len(chunks) > 1
    assert [c.chunk_index for c in chunks] == list(range(len(chunks)))


def test_empty_markdown_returns_no_chunks() -> None:
    assert _chunker().chunk("", document_id=uuid4()) == []
