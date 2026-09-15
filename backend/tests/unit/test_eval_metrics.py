"""评估指标计算测试（纯函数）。"""

import pytest

from app.services.eval.metrics import (
    aggregate_metrics,
    citation_stats,
    first_hit_rank,
    is_refusal,
    ndcg_at_k,
    point_coverage,
    recall_flags,
)


def test_recall_flags() -> None:
    flags = recall_flags(["a", "b", "c"], {"c"}, ks=(1, 2, 3))
    assert flags == {"recall@1": False, "recall@2": False, "recall@3": True}


def test_first_hit_rank_and_ndcg() -> None:
    assert first_hit_rank(["a", "b", "c"], {"b"}) == 2
    assert first_hit_rank(["a"], {"b"}) is None
    assert ndcg_at_k(["a", "b"], {"b"}, k=2) == pytest.approx(0.6309297535714574)


def test_citation_stats() -> None:
    stats = citation_stats(["a", "b", "x"], {"a", "b", "c"})
    assert stats["precision"] == 2 / 3
    assert stats["recall"] == 2 / 3


def test_refusal_and_point_coverage() -> None:
    assert is_refusal("资料不足，无法回答。", [])
    assert not is_refusal("这是答案 [1]", [])
    assert point_coverage(["40.2 元/股", "员工持股"], "价格上限调整为40.2元/股") == 0.5


def test_aggregate_metrics() -> None:
    rows = [
        {"recall@10": True, "mrr": 1.0, "durations": {"total": 100.0}},
        {"recall@10": False, "mrr": 0.0, "durations": {"total": 200.0}},
    ]
    agg = aggregate_metrics(rows)
    assert agg["recall@10"] == 0.5
    assert agg["mrr"] == 0.5
    assert agg["latency_p50_ms"] == 150.0
