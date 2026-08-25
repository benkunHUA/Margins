"""MinerU 解析服务测试（注入 fake client，不触网）。"""

from pathlib import Path

from app.core.config import ParserConfig
from app.services.parsing import MineruOnlineParser, ParsedDocument


class FakeMineruClient:
    def __init__(self) -> None:
        self.flash_sources: list[str] = []
        self.extract_sources: list[str] = []

    def flash_extract(self, source: str, **kwargs) -> dict:
        self.flash_sources.append(source)
        return {"markdown": "# flash 结果", "state": "done"}

    def extract(self, source: str, **kwargs) -> dict:
        self.extract_sources.append(source)
        return {"markdown": "# extract 结果", "state": "done", "images": []}


async def test_small_file_uses_flash(tmp_path: Path) -> None:
    client = FakeMineruClient()
    parser = MineruOnlineParser(ParserConfig(mineru_api_token="t"), client=client)
    f = tmp_path / "small.md"
    f.write_text("x" * 100, encoding="utf-8")

    result = await parser.parse(f, file_type="md")
    assert isinstance(result, ParsedDocument)
    assert result.markdown == "# flash 结果"
    assert client.flash_sources == [str(f)]


async def test_large_file_uses_extract(tmp_path: Path) -> None:
    client = FakeMineruClient()
    parser = MineruOnlineParser(
        ParserConfig(mineru_api_token="t", flash_max_size_mb=1),
        client=client,
    )
    f = tmp_path / "big.pdf"
    f.write_bytes(b"\x00" * (2 * 1024 * 1024))

    result = await parser.parse(f, file_type="pdf")
    assert result.markdown == "# extract 结果"
    assert client.extract_sources == [str(f)]
