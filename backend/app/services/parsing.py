"""文档解析：MinerU 在线解析服务封装。"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from app.core.config import ParserConfig
from app.core.exceptions import NotImplementedStageError


class ParsedDocument(BaseModel):
    markdown: str
    images: list[Path] = []
    meta: dict[str, Any] = {}


class MineruParser(ABC):
    @abstractmethod
    async def parse(self, file_path: Path, *, file_type: str) -> ParsedDocument: ...


class MineruOnlineParser(MineruParser):
    """基于 mineru-open-sdk 的在线解析实现（M1 落地）。

    - 小文件（≤10MB / ≤20 页）走 flash_extract 快速通道；
    - 其余走 extract（需 MINERU_API_TOKEN）。
    """

    def __init__(self, config: ParserConfig) -> None:
        self._config = config
        self._client = None  # M1: from mineru import MinerU

    async def parse(self, file_path: Path, *, file_type: str) -> ParsedDocument:
        raise NotImplementedStageError("M1: MinerU 在线解析")
