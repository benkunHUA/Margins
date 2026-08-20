"""查询重写组件。"""

from abc import ABC, abstractmethod
from collections.abc import Sequence

from app.core.config import RetrievalConfig
from app.core.exceptions import NotImplementedStageError
from app.domain.entities import Message
from app.services.llm import LLMClient


class QueryRewriter(ABC):
    @abstractmethod
    async def rewrite(self, question: str, history: Sequence[Message]) -> list[str]: ...


class LLMQueryRewriter(QueryRewriter):
    """M3 落地：ChatOpenAI 结构化输出多查询改写（含指代消解与复合问题拆分）。"""

    def __init__(self, llm: LLMClient, config: RetrievalConfig) -> None:
        self._llm = llm
        self._config = config

    async def rewrite(self, question: str, history: Sequence[Message]) -> list[str]:
        raise NotImplementedStageError("M3: 查询重写")
