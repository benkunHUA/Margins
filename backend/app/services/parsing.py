"""文档解析：MinerU 在线解析服务封装（mineru-open-sdk）。"""

import asyncio
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from mineru import MinerU
from pydantic import BaseModel

from app.core.config import ParserConfig


class ParsedDocument(BaseModel):
    markdown: str
    images: list[Path] = []
    meta: dict[str, Any] = {}


class MineruParser(ABC):
    @abstractmethod
    async def parse(
        self,
        file_path: Path,
        *,
        file_type: str,
        images_dir: Path | None = None,
        force_extract: bool = False,
    ) -> ParsedDocument: ...

    @property
    def supports_full_extract(self) -> bool:
        """完整 extract 通道是否可用（需要 MinerU API Token）。"""
        return False


class MineruOnlineParser(MineruParser):
    """按大小与页数路由：PDF 页数 ≤flash_max_pages 且大小 ≤flash_max_size_mb 走 flash，
    否则走 extract。"""

    def __init__(self, config: ParserConfig, client: MinerU | None = None) -> None:
        self._config = config
        self._client = client or MinerU(config.mineru_api_token)

    @property
    def supports_full_extract(self) -> bool:
        return bool(self._config.mineru_api_token)

    async def parse(
        self,
        file_path: Path,
        *,
        file_type: str,
        images_dir: Path | None = None,
        force_extract: bool = False,
    ) -> ParsedDocument:
        size_mb = file_path.stat().st_size / 1024 / 1024
        pages = _count_pdf_pages(file_path)
        source = str(file_path)
        if not force_extract and _should_use_flash(size_mb, pages, self._config):
            result = await asyncio.to_thread(self._client.flash_extract, source)
        else:
            result = await asyncio.to_thread(self._client.extract, source)

        markdown = _markdown(result)
        if _state(result) == "done" and markdown:
            images: list[Path] = []
            if images_dir is not None:
                images = await asyncio.to_thread(_persist_images, result, images_dir)
            return ParsedDocument(markdown=markdown, images=images, meta=_meta(result))
        raise ValueError(_failure_message(file_path, result))


def _should_use_flash(size_mb: float, pages: int | None, config: ParserConfig) -> bool:
    if size_mb > config.flash_max_size_mb:
        return False
    if pages is None:
        return True  # 非 PDF 或页数不可得时按大小路由（原有行为）
    return pages <= config.flash_max_pages


def _count_pdf_pages(file_path: Path) -> int | None:
    """返回 PDF 页数；非 PDF 或解析失败返回 None。"""
    if file_path.suffix.lower() != ".pdf":
        return None
    try:
        from pypdf import PdfReader

        return len(PdfReader(str(file_path)).pages)
    except Exception:
        return None


def _field(result, name: str, default=None):
    if isinstance(result, dict):
        return result.get(name, default)
    return getattr(result, name, default)


def _markdown(result) -> str:
    return (_field(result, "markdown") or "").strip()


def _state(result) -> str:
    return _field(result, "state", "") or ""


def _meta(result) -> dict[str, Any]:
    if isinstance(result, dict):
        return {k: v for k, v in result.items() if k not in ("markdown", "images")}
    return {}


def _persist_images(result, images_dir: Path) -> list[Path]:
    """把 extract 结果里的图片字节落盘，返回保存后的路径列表。"""
    images_dir.mkdir(parents=True, exist_ok=True)
    saved: list[Path] = []
    for image in _field(result, "images") or []:
        name = Path(str(_field(image, "name", ""))).name
        data = _field(image, "data")
        if not name or not isinstance(data, bytes):
            continue
        target = images_dir / name
        target.write_bytes(data)
        saved.append(target)
    return saved


def _failure_message(file_path: Path, result) -> str:
    state = _state(result)
    err_code = _field(result, "err_code", "") or ""
    error = _field(result, "error") or ""
    has_error = bool(state or err_code or error)
    detail = (
        f"state={state}, err_code={err_code}, error={error}" if has_error else "结果为空"
    )
    hint = ""
    low = f"{err_code} {error}".lower()
    if any(keyword in low for keyword in ("auth", "token", "api key", "apikey", "401", "403")):
        hint = "（请检查 .env 中的 MINERU_API_TOKEN）"
    return f"MinerU 解析失败: {file_path.name} [{detail}]{hint}"
