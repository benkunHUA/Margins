"""Markdown 图片占位符/引用的文字化替换（纯函数，便于单测）。

flash 通道丢图后留下 HTML 注释占位符（<!-- image -->）；
extract 通道的 markdown 用 ![](images/<name>) 或 <img src="images/<name>"> 引用图片。
"""

import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

_PLACEHOLDER_RE = re.compile(r"<!--\s*image\s*-->", re.IGNORECASE)
_MD_IMAGE_RE = re.compile(r"!\[[^\]]*\]\(\s*([^)\s]+)(?:\s+[\"'][^)]*[\"'])?\s*\)")
_HTML_IMG_RE = re.compile(
    r"<img\b[^>]*?\bsrc\s*=\s*[\"']([^\"']+)[\"'][^>]*>", re.IGNORECASE | re.DOTALL
)


@dataclass(frozen=True)
class EnrichmentResult:
    markdown: str
    replaced: int  # 成功替换的图片引用数
    appended: int  # 文末补充的“未定位”图片数


def contains_image_placeholder(markdown: str) -> bool:
    """flash 通道在丢图位置留下的 HTML 注释占位符。"""
    return bool(markdown) and _PLACEHOLDER_RE.search(markdown) is not None


def enrich_markdown_with_summaries(
    markdown: str,
    summaries: Mapping[str, str],
) -> EnrichmentResult:
    """把 summaries（键=图片文件名，值=文字总结）替换进 markdown 原图位置。

    支持 Markdown 图片语法 ![](path) 与 <img src="path">；找不到引用的图片
    以“图片说明：”段落追加到文末兜底，避免图片内容丢失。
    """
    text = markdown or ""
    if not summaries:
        return EnrichmentResult(markdown=text, replaced=0, appended=0)

    used: set[str] = set()
    replaced = 0

    def _sub_md(match: re.Match) -> str:
        nonlocal replaced
        name = _file_name(match.group(1))
        if name in summaries:
            used.add(name)
            replaced += 1
            return f"\n\n{summaries[name].strip()}\n\n"
        return match.group(0)

    text = _MD_IMAGE_RE.sub(_sub_md, text)

    def _sub_html(match: re.Match) -> str:
        nonlocal replaced
        name = _file_name(match.group(1))
        if name in summaries:
            used.add(name)
            replaced += 1
            return f"\n\n{summaries[name].strip()}\n\n"
        return match.group(0)

    text = _HTML_IMG_RE.sub(_sub_html, text)

    tails = [
        f"\n\n图片说明：{summaries[name].strip()}\n"
        for name in summaries
        if name not in used
    ]
    return EnrichmentResult(
        markdown=text + "".join(tails),
        replaced=replaced,
        appended=len(tails),
    )


def _file_name(ref: str) -> str:
    return Path(ref.strip().strip("\"'")).name
