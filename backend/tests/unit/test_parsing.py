"""MinerU 解析服务测试（注入 fake client，不触网；按页数路由）。"""

from pathlib import Path

import pytest

from app.core.config import ParserConfig
from app.services.parsing import MineruOnlineParser, ParsedDocument


def _build_pdf(pages: int) -> bytes:
    """生成最小合法 PDF（仅页骨架，用于数页数）。"""
    kids = " ".join(f"{i} 0 R" for i in range(3, 3 + pages))
    objs = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        f"<< /Type /Pages /Kids [{kids}] /Count {pages} >>".encode(),
    ]
    for _ in range(pages):
        objs.append(b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] >>")

    out = bytearray(b"%PDF-1.4\n")
    offsets: list[int] = []
    for idx, body in enumerate(objs, start=1):
        offsets.append(len(out))
        out += f"{idx} 0 obj\n".encode() + body + b"\nendobj\n"
    xref_pos = len(out)
    out += f"xref\n0 {len(objs) + 1}\n".encode()
    out += b"0000000000 65535 f \n"
    for off in offsets:
        out += f"{off:010d} 00000 n \n".encode()
    trailer = f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{xref_pos}\n%%EOF\n"
    out += trailer.encode()
    return bytes(out)


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


def test_mineru_constructed_with_api_token(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class FakeMinerU:
        def __init__(self, token: str | None = None, **kwargs) -> None:
            captured["token"] = token

    monkeypatch.setattr("app.services.parsing.MinerU", FakeMinerU)
    MineruOnlineParser(ParserConfig(mineru_api_token="sk-123"))
    assert captured["token"] == "sk-123"


def test_injected_client_skips_constructor(monkeypatch) -> None:
    called = False

    class FakeMinerU:
        def __init__(self, *args, **kwargs) -> None:
            nonlocal called
            called = True

    monkeypatch.setattr("app.services.parsing.MinerU", FakeMinerU)
    MineruOnlineParser(
        ParserConfig(mineru_api_token="t"),
        client=FakeMineruClient(),
    )
    assert called is False


async def test_small_non_pdf_uses_flash(tmp_path: Path) -> None:
    client = FakeMineruClient()
    parser = MineruOnlineParser(ParserConfig(mineru_api_token="t"), client=client)
    f = tmp_path / "small.md"
    f.write_text("x" * 100, encoding="utf-8")

    result = await parser.parse(f, file_type="md")
    assert isinstance(result, ParsedDocument)
    assert result.markdown == "# flash 结果"
    assert client.flash_sources == [str(f)]
    assert client.extract_sources == []


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
    assert client.flash_sources == []


async def test_pdf_with_few_pages_uses_flash(tmp_path: Path) -> None:
    client = FakeMineruClient()
    parser = MineruOnlineParser(ParserConfig(mineru_api_token="t"), client=client)
    f = tmp_path / "few.pdf"
    f.write_bytes(_build_pdf(1))

    result = await parser.parse(f, file_type="pdf")
    assert result.markdown == "# flash 结果"
    assert client.flash_sources == [str(f)]
    assert client.extract_sources == []


async def test_pdf_many_pages_uses_extract(tmp_path: Path) -> None:
    client = FakeMineruClient()
    parser = MineruOnlineParser(ParserConfig(mineru_api_token="t"), client=client)
    f = tmp_path / "many.pdf"
    f.write_bytes(_build_pdf(21))

    result = await parser.parse(f, file_type="pdf")
    assert result.markdown == "# extract 结果"
    assert client.extract_sources == [str(f)]
    assert client.flash_sources == []


async def test_flash_failure_does_not_fallback(tmp_path: Path) -> None:
    client = FakeMineruClientWithFailures(
        flash_result={"state": "failed", "err_code": "-30003", "error": "page limit"},
    )
    parser = MineruOnlineParser(ParserConfig(mineru_api_token="t"), client=client)
    f = tmp_path / "few.pdf"
    f.write_bytes(_build_pdf(1))

    with pytest.raises(ValueError, match="-30003"):
        await parser.parse(f, file_type="pdf")
    assert client.extract_sources == []  # 按页数路由，不做失败回退


async def test_parse_failure_reports_real_error_with_token_hint(tmp_path: Path) -> None:
    client = FakeMineruClientWithFailures(
        extract_result={"state": "failed", "err_code": "-10001", "error": "InvalidApiKey"},
    )
    parser = MineruOnlineParser(ParserConfig(mineru_api_token=""), client=client)
    f = tmp_path / "many.pdf"
    f.write_bytes(_build_pdf(21))

    with pytest.raises(ValueError, match="-10001"):
        await parser.parse(f, file_type="pdf")
    with pytest.raises(ValueError, match="MINERU_API_TOKEN"):
        await parser.parse(f, file_type="pdf")


class FakeMineruClientWithImages(FakeMineruClient):
    def __init__(self, images: list[dict] | None = None) -> None:
        super().__init__()
        self._images = images or []

    def extract(self, source: str, **kwargs) -> dict:
        self.extract_sources.append(source)
        return {
            "markdown": "# extract 结果\n\n![](images/a.png)",
            "state": "done",
            "images": self._images,
        }


async def test_extract_persists_images_into_images_dir(tmp_path: Path) -> None:
    client = FakeMineruClientWithImages([{"name": "a.png", "data": b"\x89PNG-image-data"}])
    parser = MineruOnlineParser(ParserConfig(mineru_api_token="t"), client=client)
    f = tmp_path / "many.pdf"
    f.write_bytes(_build_pdf(21))
    images_dir = tmp_path / "out" / "images"

    result = await parser.parse(f, file_type="pdf", images_dir=images_dir)

    assert result.images == [images_dir / "a.png"]
    assert (images_dir / "a.png").read_bytes() == b"\x89PNG-image-data"
    assert "![](images/a.png)" in result.markdown


async def test_force_extract_bypasses_flash_route(tmp_path: Path) -> None:
    client = FakeMineruClient()
    parser = MineruOnlineParser(ParserConfig(mineru_api_token="t"), client=client)
    f = tmp_path / "few.pdf"
    f.write_bytes(_build_pdf(1))

    result = await parser.parse(f, file_type="pdf", force_extract=True)

    assert result.markdown == "# extract 结果"
    assert client.extract_sources == [str(f)]
    assert client.flash_sources == []


def test_supports_full_extract_depends_on_token() -> None:
    assert MineruOnlineParser(ParserConfig(mineru_api_token="t")).supports_full_extract is True
    assert MineruOnlineParser(ParserConfig(mineru_api_token="")).supports_full_extract is False
