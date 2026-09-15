"""gold 解析：chunk_id 优先，其次 snippet（最短 chunk），再 keywords（命中最多）。"""

import re
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from uuid import UUID

from app.domain.entities import Chunk, EvalGold, EvalItemPayload
from app.domain.enums import ResolutionSource


@dataclass
class GoldResolution:
    chunk_ids: list[UUID] = field(default_factory=list)
    source: ResolutionSource = ResolutionSource.INVALID
    relocated: bool = False
    invalid: bool = False


@dataclass
class ItemGoldResolution:
    chunk_ids: list[UUID] = field(default_factory=list)
    source: ResolutionSource = ResolutionSource.INVALID
    relocated: bool = False
    invalid: bool = False


def _norm(text: str) -> str:
    return re.sub(r"\s+", "", text)


def resolve_gold(gold: EvalGold, *, chunks: list[Chunk]) -> GoldResolution:
    by_id = {str(chunk.id): chunk for chunk in chunks}
    if gold.chunk_id is not None and str(gold.chunk_id) in by_id:
        return GoldResolution(chunk_ids=[gold.chunk_id], source=ResolutionSource.CHUNK_ID)
    if gold.snippet:
        needle = _norm(gold.snippet)
        hits = [c for c in chunks if needle and needle in _norm(c.content)]
        if hits:
            best = min(hits, key=lambda c: (len(c.content), c.chunk_index))
            return GoldResolution(
                chunk_ids=[best.id],
                source=ResolutionSource.SNIPPET,
                relocated=True,
            )
    if gold.keywords:
        needles = [_norm(k) for k in gold.keywords if k.strip()]
        scored: list[tuple[int, int, Chunk]] = []
        for chunk in chunks:
            content = _norm(chunk.content)
            score = sum(1 for needle in needles if needle and needle in content)
            if score:
                scored.append((score, -len(chunk.content), chunk))
        if scored:
            scored.sort(key=lambda item: (item[0], item[1]), reverse=True)
            return GoldResolution(
                chunk_ids=[scored[0][2].id],
                source=ResolutionSource.KEYWORDS,
                relocated=True,
            )
    return GoldResolution(source=ResolutionSource.INVALID, invalid=True)


def resolve_item_gold(
    item: EvalItemPayload,
    *,
    chunks_by_doc_title: dict[str, list[Chunk]],
) -> ItemGoldResolution:
    if item.category == "no_answer":
        return ItemGoldResolution(source=ResolutionSource.INVALID)
    resolutions = [
        resolve_gold(gold, chunks=_lookup_chunks(gold.doc_title, chunks_by_doc_title))
        for gold in item.gold
    ]
    chunk_ids: list[UUID] = []
    for resolution in resolutions:
        chunk_ids.extend(resolution.chunk_ids)
    if all(resolution.invalid for resolution in resolutions):
        return ItemGoldResolution(source=ResolutionSource.INVALID, invalid=True)
    if any(r.source == ResolutionSource.KEYWORDS for r in resolutions):
        source = ResolutionSource.KEYWORDS
    elif any(r.source == ResolutionSource.SNIPPET for r in resolutions):
        source = ResolutionSource.SNIPPET
    else:
        source = ResolutionSource.CHUNK_ID
    return ItemGoldResolution(
        chunk_ids=list(dict.fromkeys(chunk_ids)),
        source=source,
        relocated=source != ResolutionSource.CHUNK_ID,
    )


def _lookup_chunks(
    doc_title: str,
    chunks_by_doc_title: dict[str, list[Chunk]],
) -> list[Chunk]:
    """文档名容错匹配：精确 → 去空白相等 → 互相包含 → 相似度 ≥0.8。"""
    if doc_title in chunks_by_doc_title:
        return chunks_by_doc_title[doc_title]
    target = _norm(doc_title)
    normalized = {_norm(title): chunks for title, chunks in chunks_by_doc_title.items()}
    if target in normalized:
        return normalized[target]
    for title, chunks in normalized.items():
        if target and (target in title or title in target):
            return chunks
    best_title = ""
    best_ratio = 0.0
    for title in normalized:
        ratio = SequenceMatcher(None, target, title).ratio()
        if ratio > best_ratio:
            best_title, best_ratio = title, ratio
    if best_ratio >= 0.8:
        return normalized[best_title]
    return []
