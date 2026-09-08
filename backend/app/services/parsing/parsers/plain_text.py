"""纯文本本地解析：TXT/Markdown 直读，PDF 用 pypdf 抽取文本层。"""

import re
from pathlib import Path

from pypdf import PdfReader

from app.services.parsing.base import DocumentParser, ParsedDocument

MIN_TEXT_CHARS = 50


class PlainTextParser(DocumentParser):
    async def parse(
        self,
        file_path: Path,
        *,
        file_type: str,
        images_dir: Path | None = None,
        force_extract: bool = False,
    ) -> ParsedDocument:
        if file_type in ("txt", "md"):
            text = file_path.read_text(encoding="utf-8", errors="replace")
        elif file_type == "pdf":
            pages: list[str] = []
            reader = PdfReader(str(file_path))
            for page in reader.pages:
                pages.append(page.extract_text() or "")
            text = "\n\n".join(pages)
        else:
            raise ValueError(f"PlainTextParser 不支持的文件类型: {file_type}")
        text = _normalize(text)
        if file_type == "pdf" and len(re.sub(r"\s", "", text)) < MIN_TEXT_CHARS:
            raise ValueError("该 PDF 未检测到文本层（可能为扫描件），请改用 MinerU 解析")
        return ParsedDocument(markdown=text, images=[], meta={"parse_mode": "plain_text"})


def _normalize(text: str) -> str:
    lines: list[str] = []
    for raw in text.replace("\ufeff", "").splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.isdigit():  # 独立页码行
            continue
        lines.append(line)
    return "\n\n".join(lines)
