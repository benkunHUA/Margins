"""MinerU 解析服务测试（注入 fake client，不触网）。"""

from pathlib import Path

import pytest

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


class FakeMineruClientWithFailures(FakeMineruClient):
    def __init__(self, flash_result: dict | None = None, extract_result: dict | None = None):
        super().__init__()
        self._flash_result = flash_result
        self._extract_result = extract_result

    def flash_extract(self, source: str, **kwargs) -> dict:
        if self._flash_result is not None:
            self.flash_sources.append(source)
            return self._flash_result
        return super().flash_extract(source, **kwargs)

    def extract(self, source: str, **kwargs) -> dict:
        if self._extract_result is not None:
            self.extract_sources.append(source)
            return self._extract_result
        return super().extract(source, **kwargs)


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


async def test_flash_failure_falls_back_to_extract(tmp_path: Path) -> None:
    client = FakeMineruClientWithFailures(
        flash_result={"state": "failed", "err_code": "-30003", "error": "page limit"},
    )
    parser = MineruOnlineParser(ParserConfig(mineru_api_token="t"), client=client)
    f = tmp_path / "big.pdf"
    f.write_bytes(b"x" * 100)

    result = await parser.parse(f, file_type="pdf")
    assert result.markdown == "# extract 结果"
    assert len(client.flash_sources) == 1
    assert len(client.extract_sources) == 1


async def test_parse_failure_reports_real_error(tmp_path: Path) -> None:
    client = FakeMineruClientWithFailures(
        flash_result={"state": "failed", "err_code": "-30003", "error": "page limit"},
        extract_result={"state": "failed", "err_code": "-10001", "error": "InvalidApiKey"},
    )
    parser = MineruOnlineParser(ParserConfig(mineru_api_token=""), client=client)
    f = tmp_path / "big.pdf"
    f.write_bytes(b"x" * 100)

    with pytest.raises(ValueError, match="-10001"):
        await parser.parse(f, file_type="pdf")
    with pytest.raises(ValueError, match="MINERU_API_TOKEN"):
        await parser.parse(f, file_type="pdf")
