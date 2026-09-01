"""查询重写组件：LLM 多查询改写（JSON 解析 + 失败降级）。"""

import json
import re
import time
from abc import ABC, abstractmethod
from collections.abc import Sequence

from app.core.config import RewriteConfig
from app.core.logging import get_logger
from app.domain.entities import Message
from app.services.llm import ChatMessage, LLMClient

logger = get_logger(__name__)

SYSTEM_PROMPT = (
    "你是检索查询改写路由器。判断用户最新问题是否需要改写；若需要，改写为一条'可直接检索'的查询。"
    "规则："
    "1. 问题完整、独立、无指代、语义明确 → 不改写，输出 {\"need_rewrite\": false}；"
    "2. 含指代（它/该公司/上述/这）→ rewrite_type=coreference，结合对话历史补全实体；"
    "3. 问题过短/含糊/口语化 → rewrite_type=expand，补充关键词、规范表述；"
    "4. 表述口语化但语义清楚 → rewrite_type=rephrase，转成检索友好句式，保持原意。"
    "要求：不改变用户意图，不编造事实；只输出 JSON："
    "{\"need_rewrite\": true, \"rewrite_type\": \"coreference|expand|rephrase\", "
    "\"rewritten_query\": \"...\"}。"
)


class QueryRewriter(ABC):
    @abstractmethod
    async def rewrite(self, question: str, history: Sequence[Message]) -> list[str]: ...


class LLMQueryRewriter(QueryRewriter):
    def __init__(self, llm: LLMClient, config: RewriteConfig) -> None:
        self._llm = llm
        self._config = config

    async def rewrite(self, question: str, history: Sequence[Message]) -> list[str]:
        start = time.perf_counter()
        if not self._config.enabled:
            logger.info(
                "查询改写已关闭",
                extra={
                    "extra_fields": {
                        "event": "rewrite",
                        "question": question,
                        "need_rewrite": False,
                        "rewrite_type": None,
                        "queries": [question],
                        "duration_ms": round((time.perf_counter() - start) * 1000, 1),
                    }
                },
            )
            return [question]

        decision: dict = {}
        try:
            history_lines = "\n".join(
                f"{'用户' if m.role.value == 'user' else '助手'}: {m.content}"
                for m in history[-self._config.history_limit :]
            )
            user = f"对话历史：\n{history_lines or '（无）'}\n最新问题：{question}"
            text = await self._llm.complete(
                [
                    ChatMessage(role="system", content=SYSTEM_PROMPT),
                    ChatMessage(role="user", content=user),
                ]
            )
            decision = _parse_decision(text)
        except Exception:
            decision = {}

        rewritten = (decision.get("rewritten_query") or "").strip()
        need_rewrite = bool(decision.get("need_rewrite")) and bool(rewritten)
        result = [rewritten] if need_rewrite else [question]
        logger.info(
            "查询改写决策",
            extra={
                "extra_fields": {
                    "event": "rewrite",
                    "question": question,
                    "need_rewrite": need_rewrite,
                    "rewrite_type": decision.get("rewrite_type") if need_rewrite else None,
                    "queries": result,
                    "duration_ms": round((time.perf_counter() - start) * 1000, 1),
                }
            },
        )
        return result


def _parse_decision(text: str) -> dict:
    match = re.search(r"\{.*\}", text, re.S)
    if not match:
        return {}
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        return {}
    if not isinstance(data, dict):
        return {}
    return {
        "need_rewrite": str(data.get("need_rewrite")).lower() in ("true", "1", "yes"),
        "rewrite_type": data.get("rewrite_type"),
        "rewritten_query": data.get("rewritten_query"),
    }
