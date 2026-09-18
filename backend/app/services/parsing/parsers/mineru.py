"""MinerU 在线解析（大小/页数路由 + extract/flash 升级 + 超长 PDF 分段合并）。"""

import asyncio
import json
import shutil
import tempfile
import time
from pathlib import Path
from typing import Any

from mineru import MinerU

from app.core.config import ParserConfig
from app.core.logging import get_logger
from app.services.image_enrichment import rename_image_refs
from app.services.parsing.base import DocumentParser, ParsedDocument

logger = get_logger(__name__)


class MineruOnlineParser(DocumentParser):
    """按大小与页数路由：PDF 页数 ≤flash_max_pages 且大小 ≤flash_max_size_mb 走 flash，
    否则走 extract；extract 单次超过 max_pages_per_call 时按页范围分段解析后合并。"""

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
        cache_dir: Path | None = None,
    ) -> ParsedDocument:
        size_mb = file_path.stat().st_size / 1024 / 1024
        pages = _count_pdf_pages(file_path)
        source = str(file_path)
        if not force_extract and _should_use_flash(size_mb, pages, self._config):
            result = await asyncio.to_thread(self._client.flash_extract, source)
            return await self._single_result(file_path, result, images_dir)

        if pages is not None and pages > self._config.max_pages_per_call:
            return await self._parse_in_parts(file_path, pages, images_dir, cache_dir)

        result = await asyncio.to_thread(self._client.extract, source)
        return await self._single_result(file_path, result, images_dir)

    async def _single_result(
        self,
        file_path: Path,
        result,
        images_dir: Path | None,
    ) -> ParsedDocument:
        """单次调用的结果校验与图片落盘（flash 与 ≤200 页 extract 共用）。"""
        markdown = _markdown(result)
        if _state(result) == "done" and markdown:
            images: list[Path] = []
            if images_dir is not None:
                images, _ = await asyncio.to_thread(_persist_images, result, images_dir)
            return ParsedDocument(markdown=markdown, images=images, meta=_meta(result))
        raise ValueError(_failure_message(file_path, result))

    async def _parse_in_parts(
        self,
        file_path: Path,
        pages: int,
        images_dir: Path | None,
        cache_dir: Path | None,
    ) -> ParsedDocument:
        """超长 PDF：按页范围串行解析，合并 markdown / 图片 / meta。

        每段的 markdown 与图片会写进段级缓存（``cache_dir``）；命中缓存的段不再调用
        MinerU，因此同一文档的重试/重新解析不必重跑已成功的段。未传 ``cache_dir``
        时用临时目录兜底（当次可用，不跨次复用）。
        """
        ranges = _page_ranges(pages, self._config.max_pages_per_call)
        total_parts = len(ranges)
        own_cache = cache_dir is None
        cache = _PartCache(cache_dir or Path(tempfile.mkdtemp(prefix="mineru-parts-")))
        markdowns: list[str] = []
        image_names: list[str] = []
        parts_meta: list[dict[str, Any]] = []

        try:
            for index, page_range in enumerate(ranges, start=1):
                started = time.perf_counter()
                cached = cache.load(page_range)
                if cached is not None:
                    part_markdown = str(cached["markdown"])
                    part_images = [
                        cache.images_dir() / name for name in cached.get("images") or []
                    ]
                    task_id = str(cached.get("task_id", ""))
                else:
                    result, part_markdown = await self._extract_part(
                        file_path, page_range, index, total_parts
                    )
                    start_page = int(page_range.split("-", 1)[0])
                    saved, rename = await asyncio.to_thread(
                        _persist_images, result, cache.images_dir(), f"p{start_page:04d}-"
                    )
                    part_markdown = rename_image_refs(part_markdown, rename)
                    part_images = saved
                    task_id = str(_field(result, "task_id", "") or "")
                    await asyncio.to_thread(
                        cache.save,
                        page_range,
                        part_markdown,
                        [path.name for path in saved],
                        task_id,
                    )

                markdowns.append(part_markdown)
                image_names.extend(path.name for path in part_images)
                parts_meta.append(
                    {
                        "index": index,
                        "pages": page_range,
                        "task_id": task_id,
                        "markdown_chars": len(part_markdown),
                        "image_count": len(part_images),
                        "cached": cached is not None,
                    }
                )
                logger.info(
                    "MinerU 分段解析完成" if cached is None else "MinerU 分段命中缓存",
                    extra={
                        "extra_fields": {
                            "event": "parse_part" if cached is None else "parse_part_cached",
                            "file": file_path.name,
                            "part": index,
                            "total_parts": total_parts,
                            "pages": page_range,
                            "cached": cached is not None,
                            "image_count": len(part_images),
                            "duration_ms": round((time.perf_counter() - started) * 1000, 1),
                        }
                    }
                )

            merged = "\n\n".join(markdowns)
            images = await asyncio.to_thread(
                _copy_part_images, cache.images_dir(), image_names, images_dir
            )
            logger.info(
                "MinerU 分段解析合并完成",
                extra={
                    "extra_fields": {
                        "event": "parse_parts_merged",
                        "file": file_path.name,
                        "part_count": total_parts,
                        "total_pages": pages,
                        "markdown_chars": len(merged),
                        "image_count": len(images),
                    }
                },
            )
            return ParsedDocument(
                markdown=merged,
                images=images,
                meta={
                    "parts": parts_meta,
                    "part_count": total_parts,
                    "total_pages": pages,
                    "pages_range": ",".join(ranges),
                }
            )
        finally:
            if own_cache:
                await asyncio.to_thread(shutil.rmtree, cache.root, ignore_errors=True)

    async def _extract_part(
        self,
        file_path: Path,
        page_range: str,
        index: int,
        total_parts: int,
    ) -> tuple[Any, str]:
        """解析单个页段；段内失败按退避重试，耗尽后抛错给上层（队列）继续兜底。"""
        attempts = max(1, self._config.part_retry_attempts)
        backoff = self._config.part_retry_backoff_seconds

        for attempt in range(1, attempts + 1):
            try:
                result = await asyncio.to_thread(
                    self._client.extract, str(file_path), pages=page_range
                )
                markdown = _markdown(result)
                if _state(result) != "done" or not markdown:
                    raise ValueError(
                        _failure_message(
                            file_path,
                            result,
                            part_note=f"第 {index}/{total_parts} 段 {page_range} 页",
                        )
                    )
                if attempt > 1:
                    logger.info(
                        "MinerU 分段重试成功",
                        extra={
                            "extra_fields": {
                                "event": "parse_part_retry_ok",
                                "file": file_path.name,
                                "part": index,
                                "total_parts": total_parts,
                                "pages": page_range,
                                "attempt": attempt,
                            }
                        },
                    )
                return result, markdown
            except Exception as exc:
                if attempt >= attempts:
                    raise
                delay = backoff[min(attempt - 1, len(backoff) - 1)] if backoff else 0.0
                logger.warning(
                    "MinerU 分段解析失败，准备重试该段",
                    extra={
                        "extra_fields": {
                            "event": "parse_part_retry",
                            "file": file_path.name,
                            "part": index,
                            "total_parts": total_parts,
                            "pages": page_range,
                            "attempt": attempt,
                            "attempts": attempts,
                            "backoff_seconds": delay,
                            "error": str(exc),
                        }
                    },
                )
                if delay > 0:
                    await asyncio.sleep(delay)

        raise RuntimeError("unreachable")  # pragma: no cover


def _page_ranges(total_pages: int, page_size: int) -> list[str]:
    """把 1..total_pages 切成每段不超过 page_size 页的页范围串。

    例：``_page_ranges(268, 200) == ["1-200", "201-268"]``。
    """
    size = max(1, page_size)
    ranges: list[str] = []
    start = 1
    while start <= total_pages:
        end = min(start + size - 1, total_pages)
        ranges.append(f"{start}-{end}")
        start = end + 1
    return ranges


class _PartCache:
    """分段解析的段级缓存（默认 `data/parsed/<doc_id>.parts/`）。

    - `part-<页范围>.json`：该段 markdown、图片文件名、MinerU task_id
    - `images/`：该段图片字节（名字已带段前缀，跨段不冲突）

    命中即可跳过该段的 MinerU 调用（省额度与时间）。解析成功由 `ParseWorker`
    删除缓存；解析最终失败则保留，便于后续只补跑失败段。
    """

    def __init__(self, root: Path) -> None:
        self.root = Path(root)

    def images_dir(self) -> Path:
        return self.root / "images"

    def _part_path(self, page_range: str) -> Path:
        return self.root / f"part-{page_range}.json"

    def load(self, page_range: str) -> dict[str, Any] | None:
        path = self._part_path(page_range)
        if not path.is_file():
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        if not isinstance(payload, dict) or not payload.get("markdown"):
            return None
        return payload

    def save(
        self,
        page_range: str,
        markdown: str,
        image_names: list[str],
        task_id: str,
    ) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        self._part_path(page_range).write_text(
            json.dumps(
                {
                    "pages": page_range,
                    "markdown": markdown,
                    "images": image_names,
                    "task_id": task_id,
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )


def _copy_part_images(
    source_dir: Path,
    names: list[str],
    images_dir: Path | None,
) -> list[Path]:
    """把段缓存里的图片复制到 `images_dir`，供图片文字总结按文件名匹配。"""
    if images_dir is None:
        return []
    images_dir.mkdir(parents=True, exist_ok=True)
    saved: list[Path] = []
    for name in names:
        source = source_dir / name
        if not source.is_file():
            continue
        target = images_dir / name
        shutil.copyfile(source, target)
        saved.append(target)
    return saved


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


def _persist_images(
    result,
    images_dir: Path,
    prefix: str = "",
) -> tuple[list[Path], dict[str, str]]:
    """把 extract 结果里的图片字节落盘。

    ``prefix`` 用于超长 PDF 分段解析：每段是独立任务，图片名会重复，
    加段前缀避免互相覆盖；返回（落盘路径，原名 -> 落盘名 映射）。
    """
    images_dir.mkdir(parents=True, exist_ok=True)
    saved: list[Path] = []
    rename: dict[str, str] = {}
    for image in _field(result, "images") or []:
        name = Path(str(_field(image, "name", ""))).name
        data = _field(image, "data")
        if not name or not isinstance(data, bytes):
            continue
        new_name = f"{prefix}{name}"
        target = images_dir / new_name
        target.write_bytes(data)
        saved.append(target)
        rename[name] = new_name
    return saved, rename


def _failure_message(file_path: Path, result, part_note: str = "") -> str:
    state = _state(result)
    err_code = _field(result, "err_code", "") or ""
    error = _field(result, "error") or ""
    has_error = bool(state or err_code or error)
    detail = (
        f"state={state}, err_code={err_code}, error={error}" if has_error else "结果为空"
    )
    where = f" [{part_note}]" if part_note else ""
    hint = ""
    low = f"{err_code} {error}".lower()
    if any(keyword in low for keyword in ("auth", "token", "api key", "apikey", "401", "403")):
        hint = "（请检查 .env 中的 MINERU_API_TOKEN）"
    return f"MinerU 解析失败: {file_path.name}{where} [{detail}]{hint}"
