"""gold 解析：chunk_id → snippet → keywords → invalid。"""

from uuid import uuid4

from app.domain.entities import Chunk, EvalGold, EvalItemPayload
from app.domain.enums import ResolutionSource
from app.services.eval.gold_resolver import resolve_gold, resolve_item_gold


def _chunk(content: str, *, chunk_index: int = 0) -> Chunk:
    return Chunk(document_id=uuid4(), chunk_index=chunk_index, content=content)


def test_resolve_by_chunk_id() -> None:
    chunk = _chunk("内容 A")
    result = resolve_gold(
        EvalGold(doc_title="a.pdf", chunk_id=chunk.id), chunks=[chunk]
    )
    assert result.source == ResolutionSource.CHUNK_ID
    assert result.chunk_ids == [chunk.id]
    assert result.relocated is False


def test_resolve_by_snippet_prefers_tightest_chunk() -> None:
    loose = _chunk("前缀" + "很长很长的内容" * 3 + "价格上限 40.2 元/股" + "后缀" * 5)
    tight = _chunk("价格上限 40.2 元/股", chunk_index=1)
    result = resolve_gold(
        EvalGold(doc_title="a.pdf", snippet="价格上限 40.2 元/股"),
        chunks=[loose, tight],
    )
    assert result.source == ResolutionSource.SNIPPET
    assert result.chunk_ids == [tight.id]
    assert result.relocated is True


def test_resolve_by_keywords_most_hits() -> None:
    weak = _chunk("员工持股计划")
    strong = _chunk("用于员工持股计划或股权激励", chunk_index=1)
    result = resolve_gold(
        EvalGold(doc_title="a.pdf", keywords=["员工持股计划", "股权激励"]),
        chunks=[weak, strong],
    )
    assert result.source == ResolutionSource.KEYWORDS
    assert result.chunk_ids == [strong.id]


def test_resolve_invalid_when_nothing_matches() -> None:
    result = resolve_gold(
        EvalGold(doc_title="a.pdf", keywords=["不存在"]), chunks=[_chunk("无关内容")]
    )
    assert result.source == ResolutionSource.INVALID
    assert result.invalid is True


def test_resolve_item_aggregates_multiple_gold() -> None:
    c1 = _chunk("回购价格上限 40.2 元/股")
    c2 = _chunk("累计回购 707,939 股", chunk_index=1)
    item = EvalItemPayload(
        id="q1",
        question="q",
        category="single_doc_fact",
        gold=[
            EvalGold(doc_title="a.pdf", chunk_id=c1.id),
            EvalGold(doc_title="a.pdf", snippet="累计回购 707,939 股"),
        ],
    )
    result = resolve_item_gold(item, chunks_by_doc_title={"a.pdf": [c1, c2]})
    assert set(result.chunk_ids) == {c1.id, c2.id}
    assert result.relocated is True
    assert result.invalid is False
