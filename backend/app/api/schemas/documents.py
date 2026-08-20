"""文档相关请求/响应模型。"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.domain.enums import DocumentStatus


class UploadResult(BaseModel):
    document_id: UUID
    filename: str
    status: DocumentStatus


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    filename: str
    file_type: str
    file_size: int
    status: DocumentStatus
    parse_error: str | None = None
    created_at: datetime
    updated_at: datetime


class DocumentDetail(DocumentOut):
    markdown: str | None = None
