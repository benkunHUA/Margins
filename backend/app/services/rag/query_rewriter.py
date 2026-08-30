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
    "你是检索查询改写助手。根据对话历史，把用户最新问题改写成多条'可直接检索'的查询。"
    "要求：1. 消解指代，将'它/这/上述'替换为具体对象；"
    "2. 复合问题拆分为独立查询；"
    "3. 用同义词/中英文术语扩展表述，关键词明确；"
    "4. 不改变用户意图，不编造事实；"
    "5. 只输出 JSON：{\"queries\": [\"q1\", \"q2\"]}。"
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
        queries: list[str] = []
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
            queries = _parse_queries(text)
        except Exception:
            queries = []

        quota = self._config.max_queries
        result: list[str] = []
        if self._config.include_original:
            result.append(question)
            quota -= 1
        for query in queries:
            if quota <= 0:
                break
            if query.strip():
                result.append(query.strip())
                quota -= 1
        result = result or [question]
        logger.info(
            "查询重写完成",
            extra={
                "extra_fields": {
                    "event": "rewrite",
                    "question": question,
                    "history_count": len(history),
                    "queries": result,
                    "duration_ms": round((time.perf_counter() - start) * 1000, 1),
                }
            },
        )
        return result


def _parse_queries(text: str) -> list[str]:
    match = re.search(r"\{.*\}", text, re.S)
    if not match:
        return []
    try:
        data = json.loads(match.group(0))
        queries = data.get("queries") if isinstance(data, dict) else None
        if isinstance(queries, list):
            return [str(q) for q in queries if str(q).strip()]
    except json.JSONDecodeError:
        pass
    return []
