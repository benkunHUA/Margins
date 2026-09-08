"""解析服务统一出口。"""

from app.services.parsing.base import DocumentParser, ParsedDocument
from app.services.parsing.parsers.mineru import MineruOnlineParser

__all__ = ["DocumentParser", "ParsedDocument", "MineruOnlineParser"]
