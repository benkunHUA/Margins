"""重排序服务：阿里云百炼 qwen3-rerank。"""

from abc import ABC, abstractmethod
from collections.abc import Sequence

from app.core.config import ModelConfig
from app.core.exceptions import NotImplementedStageError
from app.vector.base import ScoredChunk


class Reranker(ABC):
    @abstractmethod
    async def rerank(
        self,
        query: str,
        candidates: Sequence[ScoredChunk],
        *,
        top_n: int,
        threshold: float,
    ) -> list[ScoredChunk]: ...


class DashScopeReranker(Reranker):
    """M3 落地：优先 DashScopeRerank，必要时自定义 compressor 直连 SDK。"""

    def __init__(self, config: ModelConfig) -> None:
        self._config = config
        self._reranker = None  # M3: DashScopeRerank(model=qwen3-rerank)

    async def rerank(
        self,
        query: str,
        candidates: Sequence[ScoredChunk],
        *,
        top_n: int,
        threshold: float,
    ) -> list[ScoredChunk]:
        raise NotImplementedStageError("M3: qwen3-rerank 重排序")
