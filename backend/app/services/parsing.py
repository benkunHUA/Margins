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
    async def parse(self, file_path: Path, *, file_type: str) -> ParsedDocument: ...


class MineruOnlineParser(MineruParser):
    """小文件（≤flash_max_size_mb）走 flash_extract 快速通道，其余走 extract。"""

    def __init__(self, config: ParserConfig, client: MinerU | None = None) -> None:
        self._config = config
        self._client = client or MinerU()

    async def parse(self, file_path: Path, *, file_type: str) -> ParsedDocument:
        size_mb = file_path.stat().st_size / 1024 / 1024
        source = str(file_path)
        used_flash = size_mb <= self._config.flash_max_size_mb

        if used_flash:
            flash_result = await asyncio.to_thread(self._client.flash_extract, source)
            markdown = _markdown(flash_result)
            if _state(flash_result) == "done" and markdown:
                return _to_parsed(flash_result, markdown)
            # flash 失败（如页数超限）→ 回退 extract

        result = await asyncio.to_thread(self._client.extract, source)
        markdown = _markdown(result)
        if not markdown:
            raise ValueError(_failure_message(file_path, result))
        return _to_parsed(result, markdown)


def _field(result, name: str, default=None):
    if isinstance(result, dict):
        return result.get(name, default)
    return getattr(result, name, default)


def _markdown(result) -> str:
    return (_field(result, "markdown") or "").strip()


def _state(result) -> str:
    return _field(result, "state", "") or ""


def _to_parsed(result, markdown: str) -> ParsedDocument:
    meta: dict[str, Any] = {}
    if isinstance(result, dict):
        meta = {k: v for k, v in result.items() if k != "markdown"}
    return ParsedDocument(markdown=markdown, meta=meta)


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
