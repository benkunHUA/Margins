"""DashScope qwen3.8-max 图片总结服务测试（注入 fake call，不触网）。"""

from pathlib import Path

import pytest

from app.core.config import ImageSummaryConfig
from app.core.exceptions import ImageSummaryError
from app.services.image_summarizer import DashScopeImageSummarizer

_OK_RESPONSE = {
    "output": {"choices": [{"message": {"content": [{"text": "这是一张柱状图。"}]}}]}
}


def _config(**kwargs) -> ImageSummaryConfig:
    values = {"api_key": "sk-123", "model": "qwen3.8-max"}
    values.update(kwargs)
    return ImageSummaryConfig(**values)


class FakeCall:
    def __init__(self, response=_OK_RESPONSE) -> None:
        self.response = response
        self.kwargs: list[dict] = []

    def __call__(self, **kwargs):
        self.kwargs.append(kwargs)
        return self.response


async def test_summarize_image_sends_file_uri_and_extracts_text(tmp_path: Path) -> None:
    image = tmp_path / "chart.png"
    image.write_bytes(b"\x89PNG")
    call = FakeCall()
    service = DashScopeImageSummarizer(_config(), call=call)

    texts = await service.summarize_images([image])

    assert texts == ["这是一张柱状图。"]
    assert len(call.kwargs) == 1
    sent = call.kwargs[0]
    assert sent["model"] == "qwen3.8-max"
    assert sent["api_key"] == "sk-123"
    assert sent["enable_thinking"] is False
    assert sent["temperature"] == 0.2
    content = sent["messages"][0]["content"]
    assert content[0]["image"] == f"file://{image.resolve()}"
    assert "总结" in content[1]["text"]


async def test_summarize_multiple_images_in_order(tmp_path: Path) -> None:
    paths: list[Path] = []
    for name in ("a.png", "b.png"):
        p = tmp_path / name
        p.write_bytes(b"x")
        paths.append(p)
    call = FakeCall()
    service = DashScopeImageSummarizer(_config(), call=call)

    texts = await service.summarize_images(paths)

    assert len(texts) == 2
    assert len(call.kwargs) == 2
    assert call.kwargs[0]["messages"][0]["content"][0]["image"].endswith("a.png")
    assert call.kwargs[1]["messages"][0]["content"][0]["image"].endswith("b.png")


async def test_empty_images_returns_empty() -> None:
    call = FakeCall()
    service = DashScopeImageSummarizer(_config(api_key=""), call=call)
    assert await service.summarize_images([]) == []
    assert call.kwargs == []


async def test_missing_api_key_raises_before_any_call(tmp_path: Path) -> None:
    p = tmp_path / "a.png"
    p.write_bytes(b"x")
    call = FakeCall()
    service = DashScopeImageSummarizer(_config(api_key=""), call=call)

    with pytest.raises(ImageSummaryError, match="DASHSCOPE_API_KEY"):
        await service.summarize_images([p])
    assert call.kwargs == []


async def test_error_response_raises_with_detail(tmp_path: Path) -> None:
    p = tmp_path / "a.png"
    p.write_bytes(b"x")
    response = {"status_code": 400, "code": "InvalidParameter", "message": "bad image"}
    service = DashScopeImageSummarizer(_config(), call=FakeCall(response))

    with pytest.raises(ImageSummaryError, match="InvalidParameter"):
        await service.summarize_images([p])
