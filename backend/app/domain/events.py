"""RAG 管线事件流（SSE 输出模型）。"""

from dataclasses import dataclass, field

from app.domain.entities import Citation


@dataclass(frozen=True)
class RagEvent:
    pass


@dataclass(frozen=True)
class MetaEvent(RagEvent):
    session_id: str
    message_id: str


@dataclass(frozen=True)
class CitationsEvent(RagEvent):
    citations: list[Citation] = field(default_factory=list)


@dataclass(frozen=True)
class DeltaEvent(RagEvent):
    content: str


@dataclass(frozen=True)
class DoneEvent(RagEvent):
    message_id: str


@dataclass(frozen=True)
class ErrorEvent(RagEvent):
    code: str = "RAG_ERROR"
    message: str = "检索生成服务暂不可用"
