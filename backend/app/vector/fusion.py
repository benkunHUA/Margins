"""RRF（Reciprocal Rank Fusion）融合组件。

纯函数、无 IO，权重与去重逻辑可单测。
"""

from collections import defaultdict
from collections.abc import Sequence

from app.vector.base import ScoredChunk


class RRFFusion:
    def fuse(
        self,
        ranked_lists: Sequence[Sequence[ScoredChunk]],
        *,
        k: int = 60,
        top_n: int = 30,
    ) -> list[ScoredChunk]:
        """按排序位置融合多路召回，同 chunk 取最高单路分数，按融合分降序取 top_n。"""
        if not ranked_lists:
            return []

        fused: dict[str, float] = defaultdict(float)
        best: dict[str, ScoredChunk] = {}

        for ranked in ranked_lists:
            for rank, item in enumerate(ranked, start=1):
                key = str(item.chunk.id)
                fused[key] += 1.0 / (k + rank)
                if key not in best or item.score > best[key].score:
                    best[key] = item

        ordered = sorted(best.values(), key=lambda item: fused[str(item.chunk.id)], reverse=True)
        return ordered[:top_n]
