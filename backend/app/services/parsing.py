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
        if size_mb <= self._config.flash_max_size_mb:
            result = await asyncio.to_thread(self._client.flash_extract, source)
        else:
            result = await asyncio.to_thread(self._client.extract, source)

        raw = getattr(result, "markdown", None)
        if raw is None and isinstance(result, dict):
            raw = result.get("markdown")
        markdown = (raw or "").strip()
        if not markdown:
            raise ValueError(f"MinerU 解析结果为空: {file_path.name}")
        meta: dict[str, Any] = {}
        if isinstance(result, dict):
            meta = {k: v for k, v in result.items() if k != "markdown"}
        return ParsedDocument(markdown=markdown, meta=meta)
