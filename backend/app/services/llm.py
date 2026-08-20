"""LLM 客户端：LangChain 1.x ChatOpenAI（OpenAI 兼容接口）。"""

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator, Sequence

from pydantic import BaseModel

from app.core.config import ModelConfig
from app.core.exceptions import NotImplementedStageError


class ChatMessage(BaseModel):
    role: str
    content: str


class LLMClient(ABC):
    @abstractmethod
    async def stream(self, messages: Sequence[ChatMessage]) -> AsyncIterator[str]: ...


class LangChainLLMClient(LLMClient):
    """M2 落地：ChatOpenAI(base_url=LLM_BASE_URL, model=LLM_MODEL).astream()。"""

    def __init__(self, config: ModelConfig) -> None:
        self._config = config
        self._model = None  # M2: langchain_openai ChatOpenAI

    async def stream(self, messages: Sequence[ChatMessage]) -> AsyncIterator[str]:
        raise NotImplementedStageError("M2: LangChain 流式生成")
