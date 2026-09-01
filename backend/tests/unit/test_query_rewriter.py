"""查询重写路由测试（fake LLM.complete，单提示词决策）。"""

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
    defaults = dict(enabled=True, history_limit=6, temperature=0.2)
    defaults.update(overrides)
    return LLMQueryRewriter(llm, RewriteConfig(**defaults))


async def test_no_rewrite_returns_original() -> None:
    llm = FakeLLM('{"need_rewrite": false}')
    result = await _rewriter(llm).rewrite("安旭生物回购进展如何", [])
    assert result == ["安旭生物回购进展如何"]
    assert llm.prompts  # 仍做一次决策调用


async def test_rewrite_returns_single_rewritten_query() -> None:
    llm = FakeLLM(
        '{"need_rewrite": true, "rewrite_type": "coreference", '
        '"rewritten_query": "安旭生物回购股份的进展情况如何？"}'
    )
    result = await _rewriter(llm).rewrite("它的回购进展如何", [])
    assert result == ["安旭生物回购股份的进展情况如何？"]


async def test_bad_json_falls_back_to_original() -> None:
    llm = FakeLLM("不是 JSON")
    assert await _rewriter(llm).rewrite("q", []) == ["q"]


async def test_disabled_skips_llm() -> None:
    llm = FakeLLM('{"need_rewrite": true, "rewritten_query": "x"}')
    result = await _rewriter(llm, enabled=False).rewrite("q", [])
    assert result == ["q"]
    assert llm.prompts == []


async def test_rewrite_logs_decision(caplog) -> None:
    llm = FakeLLM(
        '{"need_rewrite": true, "rewrite_type": "expand", '
        '"rewritten_query": "安旭生物回购股份进展情况"}'
    )
    with caplog.at_level("INFO", logger="app.services.rag.query_rewriter"):
        await _rewriter(llm).rewrite("介绍下", [])
    record = next(
        record
        for record in caplog.records
        if getattr(record, "extra_fields", {}).get("event") == "rewrite"
    )
    assert record.extra_fields["need_rewrite"] is True
    assert record.extra_fields["rewrite_type"] == "expand"
    assert record.extra_fields["queries"] == ["安旭生物回购股份进展情况"]
