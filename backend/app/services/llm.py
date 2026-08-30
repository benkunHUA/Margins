"""LLM 客户端：LangChain 1.x ChatOpenAI（OpenAI 兼容接口，默认 DeepSeek）。"""

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator, Sequence

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from pydantic import BaseModel

from app.core.config import ModelConfig


class ChatMessage(BaseModel):
    role: str
    content: str


class LLMClient(ABC):
    @abstractmethod
    async def stream(self, messages: Sequence[ChatMessage]) -> AsyncIterator[str]: ...

    @abstractmethod
    async def complete(self, messages: Sequence[ChatMessage]) -> str: ...


def _to_lc_messages(messages: Sequence[ChatMessage]):
    return [
        HumanMessage(content=m.content)
        if m.role == "user"
        else SystemMessage(content=m.content)
        if m.role == "system"
        else AIMessage(content=m.content)
        for m in messages
    ]


class LangChainLLMClient(LLMClient):
    """model 可注入替身（测试）；默认 ChatOpenAI。"""

    def __init__(self, config: ModelConfig, model: ChatOpenAI | None = None) -> None:
        self._config = config
        self._model = model
        self._client: ChatOpenAI | None = None

    def _model_client(self) -> ChatOpenAI:
        """惰性创建：无 key 时在使用阶段报错，避免应用启动/导入即失败。"""
        if self._model is not None:
            return self._model
        if self._client is None:
            self._client = ChatOpenAI(
                model=self._config.llm_model,
                base_url=self._config.llm_base_url,
                api_key=self._config.llm_api_key,
                temperature=0.2,
            )
        return self._client

    async def stream(self, messages: Sequence[ChatMessage]) -> AsyncIterator[str]:
        async for chunk in self._model_client().astream(_to_lc_messages(messages)):
            text = getattr(chunk, "content", None)
            if isinstance(text, str) and text:
                yield text

    async def complete(self, messages: Sequence[ChatMessage]) -> str:
        response = await self._model_client().ainvoke(_to_lc_messages(messages))
        text = getattr(response, "content", "")
        return text if isinstance(text, str) else ""
