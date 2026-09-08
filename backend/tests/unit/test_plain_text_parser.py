"""PlainTextParser 测试：TXT/MD 直读、PDF pypdf 抽取、无文本层报错。"""

from pathlib import Path

import pytest

from app.services.parsing import PlainTextParser

_MIN_TEXT = "第一段正文内容。第二段正文内容。第三段正文内容用于超过阈值。" * 3


class FakePage:
    def __init__(self, text: str) -> None:
        self._text = text

    def extract_text(self) -> str:
        return self._text


class FakePdfReader:
    def __init__(self, pages: list[str]) -> None:
        self.pages = [FakePage(text) for text in pages]


async def test_txt_reads_plain_text(tmp_path: Path) -> None:
    f = tmp_path / "a.txt"
    f.write_text("\ufeff标题\n\n正文内容" + _MIN_TEXT, encoding="utf-8")
    parser = PlainTextParser()

    result = await parser.parse(f, file_type="txt")

    assert result.markdown.startswith("标题")
    assert "\ufeff" not in result.markdown
    assert result.images == []


async def test_md_reads_plain_markdown(tmp_path: Path) -> None:
    f = tmp_path / "b.md"
    f.write_text("# 标题\n\n正文" + _MIN_TEXT, encoding="utf-8")
    parser = PlainTextParser()

    result = await parser.parse(f, file_type="md")

    assert result.markdown.startswith("# 标题")


async def test_pdf_extracts_and_normalizes_pages(tmp_path: Path, monkeypatch) -> None:
    f = tmp_path / "c.pdf"
    f.write_bytes(b"%PDF")
    monkeypatch.setattr(
        "app.services.parsing.parsers.plain_text.PdfReader",
        lambda _path: FakePdfReader(["第一页正文" + _MIN_TEXT, "12\n第二页正文" + _MIN_TEXT]),
    )

    result = await PlainTextParser().parse(
        f,
        file_type="pdf",
        images_dir=tmp_path / "images",
        force_extract=True,
    )

    assert "第一页正文" in result.markdown
    assert "第二页正文" in result.markdown
    assert "\n\n12\n\n" not in result.markdown  # 独立页码行被清理
    assert result.images == []
    assert result.meta["parse_mode"] == "plain_text"


async def test_pdf_without_text_layer_raises_hint(tmp_path: Path, monkeypatch) -> None:
    f = tmp_path / "scan.pdf"
    f.write_bytes(b"%PDF")
    monkeypatch.setattr(
        "app.services.parsing.parsers.plain_text.PdfReader",
        lambda _path: FakePdfReader(["1", ""]),
    )

    with pytest.raises(ValueError, match="MinerU"):
        await PlainTextParser().parse(f, file_type="pdf")


async def test_unsupported_file_type_raises(tmp_path: Path) -> None:
    f = tmp_path / "a.docx"
    f.write_bytes(b"x")
    with pytest.raises(ValueError, match="不支持"):
        await PlainTextParser().parse(f, file_type="docx")
