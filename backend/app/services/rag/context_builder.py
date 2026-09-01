"""上下文组装：引用编号、历史、token 预算（M2 简化版）。"""

from collections.abc import Sequence

from pydantic import BaseModel

from app.core.config import RetrievalConfig
from app.domain.entities import Citation, Message
from app.domain.enums import MessageRole
from app.services.llm import ChatMessage
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
    ) -> ContextBundle:
        citations: list[Citation] = []
        refs: list[str] = []
        for index, item in enumerate(chunks[: self._config.rerank_top_n], start=1):
            chunk = item.chunk
            doc_title = chunk.metadata.get("doc_title") or "未知文档"
            citations.append(
                Citation(
                    chunk_id=chunk.id,
                    document_id=chunk.document_id,
                    doc_title=doc_title,
                    heading_path=chunk.heading_path,
                    snippet=chunk.content[:200],
                )
            )
            refs.append(
                f"【引用 {index}】《{doc_title}》/{chunk.heading_path or '无章节'}\n"
                f"{chunk.content}"
            )

        history_lines = []
        for msg in history[-self._config.history_limit :]:
            who = "用户" if msg.role == MessageRole.USER else "助手"
            history_lines.append(f"{who}: {msg.content}")

        system = (
            "你是知识库问答助手。只依据下面给出的参考资料回答，不要编造；"
            "资料不足时明确说明。引用请用 [n] 标注。"
        )
        user = (
            f"参考资料（共 {len(refs)} 条，每条以【引用 n】开头）：\n"
            + "\n\n".join(refs)
            + "\n\n对话历史：\n"
            + ("\n".join(history_lines) if history_lines else "（无）")
            + f"\n\n问题：{question}"
        )
        messages = [
            ChatMessage(role="system", content=system),
            ChatMessage(role="user", content=user),
        ]
        return ContextBundle(
            messages=[msg.model_dump() for msg in messages],
            citations=citations,
        )
