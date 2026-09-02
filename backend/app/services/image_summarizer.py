"""图片文字总结服务：百炼 qwen3.8-max（DashScope MultiModalConversation，原生多模态 VLM）。"""

import asyncio
from abc import ABC, abstractmethod
from collections.abc import Sequence
from pathlib import Path

import dashscope

from app.core.config import ImageSummaryConfig
from app.core.exceptions import ImageSummaryError
from app.core.logging import get_logger

logger = get_logger(__name__)

_SUMMARY_PROMPT = (
    "请用中文客观总结这张图片：这是什么类型的图片/图表，展示了哪些关键信息、数据或结论。"
    "直接输出内容总结（3-8 句），不要客套话、不要 Markdown 标题。"
)


class ImageSummarizer(ABC):
    @abstractmethod
    async def summarize_images(self, images: Sequence[Path]) -> list[str]:
        """按输入顺序返回每张图片的文字总结；失败抛出 ImageSummaryError。"""


class DashScopeImageSummarizer(ImageSummarizer):
    """call 可注入替身（测试）；默认 dashscope.MultiModalConversation.call。"""

    def __init__(self, config: ImageSummaryConfig, call=None) -> None:
        self._config = config
        self._call = call or dashscope.MultiModalConversation.call

    async def summarize_images(self, images: Sequence[Path]) -> list[str]:
        if not images:
            return []
        if not self._config.api_key:
            raise ImageSummaryError(
                "图片文字总结需要配置 DASHSCOPE_API_KEY（env: DASHSCOPE_API_KEY）"
            )
        summaries: list[str] = []
        for index, path in enumerate(images, start=1):
            logger.info("图片文字总结开始: %s (%d/%d)", path.name, index, len(images))
            response = await asyncio.to_thread(
                self._call,
                model=self._config.model,
                api_key=self._config.api_key,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"image": f"file://{path.resolve()}"},
                            {"text": _SUMMARY_PROMPT},
                        ],
                    }
                ],
                enable_thinking=self._config.thinking,
                temperature=self._config.temperature,
                max_tokens=self._config.max_tokens,
            )
            summaries.append(_extract_text(response))
            logger.info("图片文字总结完成: %s", path.name)
        return summaries


def _field(obj, name: str, default=None):
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _extract_text(response) -> str:
    output = _field(response, "output")
    choices = _field(output, "choices") or []
    if not choices:
        raise ImageSummaryError(f"图片总结响应为空: {_error_detail(response)}")
    message = _field(choices[0], "message") or {}
    content = _field(message, "content")
    if isinstance(content, list) and content:
        text = _field(content[0], "text", "")
    elif isinstance(content, str):
        text = content
    else:
        text = ""
    text = (text or "").strip()
    if not text:
        raise ImageSummaryError(f"图片总结响应缺少文本: {_error_detail(response)}")
    return text


def _error_detail(response) -> str:
    status = _field(response, "status_code", "") or ""
    code = _field(response, "code", "") or ""
    message = _field(response, "message", "") or ""
    return (
        f"status={status}, code={code}, message={message}"
        if (status or code or message)
        else "响应为空"
    )
