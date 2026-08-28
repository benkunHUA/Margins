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


class LangChainLLMClient(LLMClient):
    """model 可注入替身（测试）；默认 ChatOpenAI。"""

    def __init__(self, config: ModelConfig, model: ChatOpenAI | None = None) -> None:
        self._config = config
        self._model = model or ChatOpenAI(
            model=config.llm_model,
            base_url=config.llm_base_url,
            api_key=config.llm_api_key,
            temperature=0.2,
        )

    async def stream(self, messages: Sequence[ChatMessage]) -> AsyncIterator[str]:
        lc_messages = [
            HumanMessage(content=m.content)
            if m.role == "user"
            else SystemMessage(content=m.content)
            if m.role == "system"
            else AIMessage(content=m.content)
            for m in messages
        ]
        async for chunk in self._model.astream(lc_messages):
            text = getattr(chunk, "content", None)
            if isinstance(text, str) and text:
                yield text
