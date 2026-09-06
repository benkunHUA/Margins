"""领域实体。

实体是各层间传递的唯一数据形态（Pydantic 模型），ORM 模型不得泄漏到服务层。
"""

from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

from app.domain.enums import DocumentStatus, MessageRole, ParseJobStatus


def _now() -> datetime:
    return datetime.now(UTC)


class Citation(BaseModel):
    chunk_id: UUID
    document_id: UUID
    doc_title: str
    heading_path: str | None = None
    snippet: str


class QueryLogStep(BaseModel):
    """链路中的单个阶段（stage 为 rewrite/hybrid/rerank/context/llm）。"""

    stage: str
    label: str
    duration_ms: float = 0
    summary: str = ""
    data: dict[str, Any] = Field(default_factory=dict)


class QueryLog(BaseModel):
    """一次问答的完整检索链路记录。"""

    id: UUID = Field(default_factory=uuid4)
    session_id: UUID
    session_title: str = ""
    question: str
    status: str = "success"
    error: str | None = None
    total_ms: float = 0.0
    answer: str | None = None
    steps: list[QueryLogStep] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=_now)


class Document(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    id: UUID = Field(default_factory=uuid4)
    filename: str
    file_type: str
    file_size: int
    file_path: Path
    markdown_path: Path | None = None
    status: DocumentStatus = DocumentStatus.PENDING
    parse_error: str | None = None
    extra: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)


class Chunk(BaseModel):
    """检索最小单元；id 同时作为 Faiss 向量 id。"""

    id: UUID = Field(default_factory=uuid4)
    document_id: UUID
    chunk_index: int
    content: str
    heading_path: str | None = None
    page: int | None = None
    token_count: int | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class Session(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    title: str = "新会话"
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)


class Message(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    session_id: UUID
    role: MessageRole
    content: str
    citations: list[Citation] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=_now)


class ParseJob(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    document_id: UUID
    status: ParseJobStatus = ParseJobStatus.QUEUED
    attempt: int = 0
    last_error: str | None = None
    queued_at: datetime = Field(default_factory=_now)
    started_at: datetime | None = None
    finished_at: datetime | None = None


class Page[T](BaseModel):
    items: list[T]
    total: int
    page: int
    page_size: int
