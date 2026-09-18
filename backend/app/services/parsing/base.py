"""解析器抽象与解析结果（所有解析方式的公共协议）。"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from pydantic import BaseModel


class ParsedDocument(BaseModel):
    markdown: str
    images: list[Path] = []
    meta: dict[str, Any] = {}


class DocumentParser(ABC):
    @abstractmethod
    async def parse(
        self,
        file_path: Path,
        *,
        file_type: str,
        images_dir: Path | None = None,
        force_extract: bool = False,
        cache_dir: Path | None = None,
    ) -> ParsedDocument: ...

    @property
    def supports_full_extract(self) -> bool:
        """完整 extract 通道是否可用（仅 MinerU 有意义）。"""
        return False
