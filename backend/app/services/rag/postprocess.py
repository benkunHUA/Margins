"""RAG 结果后处理：跨查询去重合并、每文档限量、引用过滤（管线与评估共用）。"""

import re
from collections.abc import Sequence

from app.index.values import ScoredChunk

CITATION_MARKER = re.compile(r"[\[【]\s*(?:引用|参考|文献)?\s*(\d{1,2})\s*[\]】]")


def merge_candidates(result_lists: Sequence[list[ScoredChunk]]) -> list[ScoredChunk]:
    merged: dict[str, ScoredChunk] = {}
    for items in result_lists:
        for item in items:
            key = str(item.chunk.id)
            if key not in merged or item.score > merged[key].score:
                merged[key] = item
    return list(merged.values())


def cap_per_document(items: Sequence[ScoredChunk], cap: int) -> list[ScoredChunk]:
    counts: dict[str, int] = {}
    result: list[ScoredChunk] = []
    for item in items:
        key = str(item.chunk.document_id)
        if counts.get(key, 0) >= cap:
            continue
        counts[key] = counts.get(key, 0) + 1
        result.append(item)
    return result


def filter_citations(citations: list, answer: str, cap: int) -> list:
    """只保留回答中实际引用的 [n]（兼容 [引用 n]/【n】），按首次出现去重并截断。"""
    picked: list[int] = []
    for marker in CITATION_MARKER.findall(answer):
        index = int(marker)
        if 1 <= index <= len(citations) and index - 1 not in picked:
            picked.append(index - 1)
            if len(picked) >= cap:
                break
    return [citations[i] for i in picked]
