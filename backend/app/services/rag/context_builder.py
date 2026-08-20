"""上下文组装：引用编号、token 预算裁剪。"""

from collections.abc import Sequence

from pydantic import BaseModel

from app.core.config import RetrievalConfig
from app.core.exceptions import NotImplementedStageError
from app.domain.entities import Citation, Message
from app.vector.base import ScoredChunk


class ContextBundle(BaseModel):
    messages: list[dict]
    citations: list[Citation]


class ContextBuilder:
    def __init__(self, config: RetrievalConfig) -> None:
        self._config = config

    def build(
        self,
        chunks: Sequence[ScoredChunk],
        history: Sequence[Message],
        question: str,
        *,
        token_budget: int,
    ) -> ContextBundle:
        raise NotImplementedStageError("M3: 上下文组装")
