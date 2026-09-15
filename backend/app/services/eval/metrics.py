"""评估指标纯函数：Recall / MRR / nDCG / 引用 / 拒答 / 要点覆盖 / 聚合。"""

import math
import re
import statistics

_REFUSAL_PHRASES = ("资料不足", "未提及", "无法回答", "没有找到", "无法确定")


def recall_flags(
    ranked_ids: list[str],
    gold_ids: set[str],
    ks: tuple[int, ...] = (5, 10, 30),
) -> dict[str, bool]:
    return {f"recall@{k}": bool(gold_ids & set(ranked_ids[:k])) for k in ks}


def first_hit_rank(ranked_ids: list[str], gold_ids: set[str]) -> int | None:
    for index, chunk_id in enumerate(ranked_ids, start=1):
        if chunk_id in gold_ids:
            return index
    return None


def ndcg_at_k(ranked_ids: list[str], gold_ids: set[str], k: int = 10) -> float:
    dcg = sum(
        1 / math.log2(rank + 1)
        for rank, chunk_id in enumerate(ranked_ids[:k], start=1)
        if chunk_id in gold_ids
    )
    ideal_hits = min(len(gold_ids), k)
    idcg = sum(1 / math.log2(rank + 1) for rank in range(1, ideal_hits + 1))
    return dcg / idcg if idcg else 0.0


def citation_stats(cited_ids: list[str], gold_ids: set[str]) -> dict[str, float]:
    if not cited_ids:
        return {"precision": 0.0, "recall": 0.0}
    hit = len(set(cited_ids) & gold_ids)
    return {
        "precision": hit / len(set(cited_ids)),
        "recall": hit / len(gold_ids) if gold_ids else 0.0,
    }


def is_refusal(answer: str, citations: list) -> bool:
    if citations:
        return False
    return any(phrase in answer for phrase in _REFUSAL_PHRASES)


def point_coverage(points: list[str], answer: str) -> float:
    if not points:
        return 0.0
    normalized = re.sub(r"\s+", "", answer)
    hit = sum(1 for point in points if re.sub(r"\s+", "", point) in normalized)
    return hit / len(points)


def aggregate_metrics(rows: list[dict]) -> dict:
    if not rows:
        return {}
    result: dict = {}
    numeric_keys = {
        key
        for row in rows
        for key in row
        if key != "durations"
    }
    for key in sorted(numeric_keys):
        values = [row[key] for row in rows if isinstance(row.get(key), bool)]
        if values:
            result[key] = round(sum(1 for value in values if value) / len(rows), 4)
            continue
        numbers = [
            float(row[key])
            for row in rows
            if isinstance(row.get(key), (int, float)) and not isinstance(row.get(key), bool)
        ]
        if numbers:
            result[key] = round(sum(numbers) / len(numbers), 4)
    totals = [
        row["durations"]["total"]
        for row in rows
        if isinstance(row.get("durations"), dict) and "total" in row["durations"]
    ]
    if totals:
        result["latency_p50_ms"] = round(statistics.median(totals), 1)
    return result
