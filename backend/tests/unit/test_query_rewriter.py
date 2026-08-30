"""查询重写测试（fake LLM.complete）。"""

from app.core.config import RewriteConfig
from app.services.llm import LLMClient
from app.services.rag.query_rewriter import LLMQueryRewriter


class FakeLLM(LLMClient):
    def __init__(self, text: str = "") -> None:
        self.text = text
        self.prompts: list[str] = []

    async def stream(self, messages):
        yield ""

    async def complete(self, messages):
        self.prompts.append(messages[-1].content)
        return self.text


def _rewriter(llm: FakeLLM, **overrides) -> LLMQueryRewriter:
    defaults = dict(num_rewrites=2, include_original=True, max_queries=5)
    defaults.update(overrides)
    config = RewriteConfig(**defaults)
    return LLMQueryRewriter(llm, config)


async def test_rewrite_returns_original_plus_queries() -> None:
    llm = FakeLLM('{"queries": ["违约金是多少？", "合同违约责任条款"]}')
    result = await _rewriter(llm).rewrite("违约金多少？", [])
    assert result == ["违约金多少？", "违约金是多少？", "合同违约责任条款"]
    assert "违约金" in llm.prompts[0]


async def test_rewrite_falls_back_on_bad_json() -> None:
    llm = FakeLLM("不是 JSON")
    result = await _rewriter(llm).rewrite("q", [])
    assert result == ["q"]


async def test_rewrite_caps_queries() -> None:
    llm = FakeLLM('{"queries": ["q1", "q2", "q3", "q4"]}')
    result = await _rewriter(llm, max_queries=3).rewrite("q", [])
    assert result == ["q", "q1", "q2"]


async def test_rewrite_logs_event(caplog) -> None:
    llm = FakeLLM('{"queries": ["q1"]}')
    with caplog.at_level("INFO", logger="app.services.rag.query_rewriter"):
        await _rewriter(llm).rewrite("q", [])
    assert any(
        getattr(record, "extra_fields", {}).get("event") == "rewrite"
        for record in caplog.records
    )
