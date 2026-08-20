"""会话相关请求/响应模型。"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.domain.entities import Citation
from app.domain.enums import MessageRole


class SessionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    created_at: datetime
    updated_at: datetime


class MessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    role: MessageRole
    content: str
    citations: list[Citation] = []
    created_at: datetime


class SessionDetail(BaseModel):
    session: SessionOut
    messages: list[MessageOut]


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=8_000)
