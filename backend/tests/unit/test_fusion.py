"""RRF 融合组件测试。"""

from uuid import UUID

from app.domain.entities import Chunk
from app.vector.base import ScoredChunk
from app.vector.fusion import RRFFusion


def _scored(chunk_id: str, score: float) -> ScoredChunk:
    return ScoredChunk(
        chunk=Chunk(
            id=UUID(chunk_id),
            document_id=UUID(int=0),
            chunk_index=0,
            content="",
        ),
        score=score,
    )


def test_empty_input_returns_empty() -> None:
    assert RRFFusion().fuse([]) == []


def test_single_list_keeps_order() -> None:
    ranked = [
        _scored("00000000-0000-0000-0000-000000000001", 0.9),
        _scored("00000000-0000-0000-0000-000000000002", 0.8),
    ]
    result = RRFFusion().fuse([ranked])
    assert [str(item.chunk.id) for item in result] == [
        "00000000-0000-0000-0000-000000000001",
        "00000000-0000-0000-0000-000000000002",
    ]


def test_present_in_both_lists_ranks_higher() -> None:
    a = _scored("00000000-0000-0000-0000-000000000001", 0.5)
    b = _scored("00000000-0000-0000-0000-000000000002", 0.5)
    c = _scored("00000000-0000-0000-0000-000000000003", 0.5)
    result = RRFFusion().fuse([[a, b], [a, c]])
    assert result[0].chunk.id == a.chunk.id


def test_duplicate_keeps_highest_single_score() -> None:
    low = _scored("00000000-0000-0000-0000-000000000001", 0.3)
    high = _scored("00000000-0000-0000-0000-000000000001", 0.9)
    result = RRFFusion().fuse([[low], [high]])
    assert len(result) == 1
    assert result[0].score == 0.9


def test_top_n_limits_results() -> None:
    ranked = [_scored(f"00000000-0000-0000-0000-00000000000{i}", 0.5) for i in range(1, 6)]
    result = RRFFusion().fuse([ranked], top_n=3)
    assert len(result) == 3
