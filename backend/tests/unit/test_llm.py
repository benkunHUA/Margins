"""LLM 客户端测试（注入 fake chat model，不触网）。"""

from app.core.config import ModelConfig
from app.services.llm import ChatMessage, LangChainLLMClient


class FakeChatModel:
    def __init__(self, tokens: list[str]) -> None:
        self.tokens = tokens
        self.calls = 0

    async def astream(self, messages):
        self.calls += 1
        for token in self.tokens:
            yield type("Chunk", (), {"content": token})()


async def test_stream_yields_tokens() -> None:
    model = FakeChatModel(["你好", "世界"])
    client = LangChainLLMClient(
        ModelConfig(llm_api_key="test", llm_base_url="https://x", llm_model="m"),
        model=model,
    )
    parts = [part async for part in client.stream([ChatMessage(role="user", content="hi")])]
    assert parts == ["你好", "世界"]
    assert model.calls == 1


async def test_stream_skips_empty_chunks() -> None:
    model = FakeChatModel(["", "a", ""])
    client = LangChainLLMClient(
        ModelConfig(llm_api_key="test", llm_base_url="https://x", llm_model="m"),
        model=model,
    )
    parts = [part async for part in client.stream([ChatMessage(role="system", content="s")])]
    assert parts == ["a"]
