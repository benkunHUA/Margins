"""超长 PDF 分段解析测试（fake client + 合成 PDF，不触网）。"""

from pathlib import Path

import pytest

from app.core.config import ParserConfig
from app.services.parsing.parsers.mineru import MineruOnlineParser, _page_ranges
from tests.unit.test_parsing import _build_pdf


class FakePagingClient:
    """按 ``pages`` 参数返回带页码标记的 markdown，并记录每次调用参数。"""

    def __init__(self, fail_pages: str | None = None, fail_times: int = 0) -> None:
        self.calls: list[dict] = []
        self.fail_pages = fail_pages
        self.fail_times = fail_times
        self._failures = 0

    def extract(self, source: str, **kwargs) -> dict:
        self.calls.append({"source": source, **kwargs})
        pages = kwargs.get("pages")
        if pages is not None and pages == self.fail_pages:
            self._failures += 1
            if self.fail_times == 0 or self._failures <= self.fail_times:
                return {"state": "failed", "err_code": "", "error": "boom", "markdown": None}
        start = (pages or "1").split("-")[0]
        return {
            "markdown": f"# 起始页 {start}\n\n![](images/img-0.png)",
            "state": "done",
            "task_id": f"task-{start}",
            "images": [{"name": "img-0.png", "data": b"\x89PNG-image-data"}],
        }

    def flash_extract(self, source: str, **kwargs) -> dict:
        raise AssertionError("超长 PDF 不应走 flash 通道")


def _config(**overrides) -> ParserConfig:
    defaults: dict = {"mineru_api_token": "t", "part_retry_backoff_seconds": (0.0, 0.0)}
    defaults.update(overrides)
    return ParserConfig(**defaults)


def test_page_ranges_splits_at_boundaries() -> None:
    assert _page_ranges(200, 200) == ["1-200"]
    assert _page_ranges(201, 200) == ["1-200", "201-201"]
    assert _page_ranges(268, 200) == ["1-200", "201-268"]
    assert _page_ranges(400, 200) == ["1-200", "201-400"]
    assert _page_ranges(401, 200) == ["1-200", "201-400", "401-401"]


async def test_long_pdf_is_parsed_in_pages_and_merged(tmp_path: Path) -> None:
    client = FakePagingClient()
    parser = MineruOnlineParser(_config(), client=client)
    f = tmp_path / "long.pdf"
    f.write_bytes(_build_pdf(268))
    images_dir = tmp_path / "out" / "images"

    result = await parser.parse(f, file_type="pdf", images_dir=images_dir)

    assert [call["pages"] for call in client.calls] == ["1-200", "201-268"]
    assert result.markdown.startswith("# 起始页 1")
    assert "# 起始页 201" in result.markdown
    assert result.markdown.index("起始页 1") < result.markdown.index("起始页 201")
    # 图片按段加前缀落盘，引用同步改写，跨段不覆盖
    assert result.images == [images_dir / "p0001-img-0.png", images_dir / "p0201-img-0.png"]
    assert (images_dir / "p0001-img-0.png").read_bytes() == b"\x89PNG-image-data"
    assert "![](images/p0001-img-0.png)" in result.markdown
    assert "![](images/p0201-img-0.png)" in result.markdown
    # meta 记录每段信息，便于排查
    assert result.meta["part_count"] == 2
    assert result.meta["total_pages"] == 268
    assert result.meta["pages_range"] == "1-200,201-268"
    assert [part["pages"] for part in result.meta["parts"]] == ["1-200", "201-268"]
    assert result.meta["parts"][0]["task_id"] == "task-1"


async def test_part_failure_reports_part_number_and_pages(tmp_path: Path) -> None:
    client = FakePagingClient(fail_pages="201-268")
    parser = MineruOnlineParser(_config(), client=client)
    f = tmp_path / "long.pdf"
    f.write_bytes(_build_pdf(268))

    with pytest.raises(ValueError) as excinfo:
        await parser.parse(f, file_type="pdf")

    message = str(excinfo.value)
    assert "第 2/2 段 201-268 页" in message
    assert "boom" in message
    # 段内重试：失败的段被重试 2 次，成功过的第 1 段不重跑
    assert [call["pages"] for call in client.calls] == ["1-200", "201-268", "201-268"]


async def test_transient_part_failure_recovers_without_reparsing_other_parts(
    tmp_path: Path,
) -> None:
    """第 2 段瞬时失败后重试成功：第 1 段（200 页）不应被重跑。"""
    client = FakePagingClient(fail_pages="201-268", fail_times=1)
    parser = MineruOnlineParser(_config(), client=client)
    f = tmp_path / "long.pdf"
    f.write_bytes(_build_pdf(268))

    result = await parser.parse(f, file_type="pdf")

    assert [call["pages"] for call in client.calls] == ["1-200", "201-268", "201-268"]
    assert result.meta["part_count"] == 2
    assert "# 起始页 201" in result.markdown


async def test_custom_part_size_splits_into_three(tmp_path: Path) -> None:
    client = FakePagingClient()
    parser = MineruOnlineParser(_config(max_pages_per_call=100), client=client)
    f = tmp_path / "long.pdf"
    f.write_bytes(_build_pdf(268))

    await parser.parse(f, file_type="pdf")

    assert [call["pages"] for call in client.calls] == ["1-100", "101-200", "201-268"]


async def test_short_pdf_still_uses_single_extract_without_pages(tmp_path: Path) -> None:
    client = FakePagingClient()
    parser = MineruOnlineParser(_config(), client=client)
    f = tmp_path / "short.pdf"
    f.write_bytes(_build_pdf(30))  # > flash_max_pages(20) 且 ≤ 200 -> 单次 extract

    result = await parser.parse(f, file_type="pdf")

    assert len(client.calls) == 1
    assert "pages" not in client.calls[0]
    assert result.markdown.startswith("# 起始页 1")


async def test_part_cache_is_reused_without_calling_mineru(tmp_path: Path) -> None:
    """已成功的段写入缓存：再次解析（重试/重新解析）直接复用，不再消耗额度。"""
    cache_dir = tmp_path / "out" / "doc.parts"
    images_dir = tmp_path / "out" / "images"
    f = tmp_path / "long.pdf"
    f.write_bytes(_build_pdf(268))

    first_client = FakePagingClient()
    await MineruOnlineParser(_config(), client=first_client).parse(
        f, file_type="pdf", images_dir=images_dir, cache_dir=cache_dir
    )

    assert len(first_client.calls) == 2
    assert (cache_dir / "part-1-200.json").is_file()
    assert (cache_dir / "images" / "p0001-img-0.png").is_file()

    class NeverCallClient(FakePagingClient):
        def extract(self, source: str, **kwargs) -> dict:
            raise AssertionError("命中段级缓存时不应再调用 MinerU")

    result = await MineruOnlineParser(_config(), client=NeverCallClient()).parse(
        f, file_type="pdf", images_dir=images_dir, cache_dir=cache_dir
    )

    assert result.meta["part_count"] == 2
    assert result.meta["pages_range"] == "1-200,201-268"
    assert "![](images/p0001-img-0.png)" in result.markdown
    assert "![](images/p0201-img-0.png)" in result.markdown
    # 缓存里的图片会复制回 images_dir，供图片文字总结使用
    assert result.images == [images_dir / "p0001-img-0.png", images_dir / "p0201-img-0.png"]
    assert (images_dir / "p0201-img-0.png").read_bytes() == b"\x89PNG-image-data"


async def test_corrupted_cache_entry_falls_back_to_mineru(tmp_path: Path) -> None:
    cache_dir = tmp_path / "out" / "doc.parts"
    cache_dir.mkdir(parents=True)
    (cache_dir / "part-1-200.json").write_text("{ 不是合法 JSON", encoding="utf-8")
    f = tmp_path / "long.pdf"
    f.write_bytes(_build_pdf(268))
    client = FakePagingClient()

    result = await MineruOnlineParser(_config(), client=client).parse(
        f, file_type="pdf", cache_dir=cache_dir
    )

    assert len(client.calls) == 2  # 两段都重新解析
    assert result.meta["part_count"] == 2
    assert (cache_dir / "part-1-200.json").is_file()  # 缓存被重写
