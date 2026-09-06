"""查询链路日志响应模型。"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.domain.entities import Citation, QueryLogStep


class QueryLogSummaryOut(BaseModel):
    id: UUID
    session_id: UUID
    session_title: str
    question: str
    status: str
    error: str | None = None
    total_ms: float
    citation_count: int = 0
    answer_excerpt: str | None = None
    created_at: datetime


class QueryLogDetailOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    session_id: UUID
    session_title: str
    question: str
    status: str
    error: str | None = None
    total_ms: float
    answer: str | None = None
    steps: list[QueryLogStep] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)
    created_at: datetime
