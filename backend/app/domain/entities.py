"""领域实体。

实体是各层间传递的唯一数据形态（Pydantic 模型），ORM 模型不得泄漏到服务层。
"""

from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.domain.enums import (
    DocumentStatus,
    EvalItemStatus,
    EvalMode,
    EvalRunStatus,
    MessageRole,
    ParseJobStatus,
    ParseMode,
    ResolutionSource,
)


def _now() -> datetime:
    return datetime.now(UTC)


class Citation(BaseModel):
    chunk_id: UUID
    document_id: UUID
    doc_title: str
    heading_path: str | None = None
    snippet: str
    reference_index: int | None = None


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
    parse_mode: ParseMode = ParseMode.MINERU
    markdown_path: Path | None = None
    status: DocumentStatus = DocumentStatus.PENDING
    parse_error: str | None = None
    extra: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)


class Chunk(BaseModel):
    """检索最小单元；id 为业务主键，idx_id 为索引键。

    `idx_id` 是同库三张索引表的连接键：它同时是 `chunk_fts` 的 rowid
    与 `chunk_vectors` 的 rowid，由 `index_seq` 单调分配（写入索引时才分配）。
    """

    id: UUID = Field(default_factory=uuid4)
    document_id: UUID
    chunk_index: int
    content: str
    idx_id: int | None = None
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


_CATEGORIES = {"single_doc_fact", "multi_paragraph", "multi_doc", "table_number", "no_answer"}


class EvalGold(BaseModel):
    doc_title: str
    chunk_id: UUID | None = None
    snippet: str | None = None
    keywords: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _require_locator(self) -> "EvalGold":
        if not (self.chunk_id or self.snippet or self.keywords):
            raise ValueError("gold 至少需要 chunk_id / snippet / keywords 之一")
        return self


class EvalItemPayload(BaseModel):
    id: str = Field(min_length=1, max_length=64)
    question: str = Field(min_length=1, max_length=2000)
    category: str
    gold: list[EvalGold] = Field(default_factory=list)
    expected_answer_points: list[str] = Field(default_factory=list)
    notes: str = ""

    @model_validator(mode="after")
    def _validate_category_and_gold(self) -> "EvalItemPayload":
        if self.category not in _CATEGORIES:
            raise ValueError(f"未知 category: {self.category}")
        if self.category == "no_answer" and self.gold:
            raise ValueError("no_answer 题不能标注 gold")
        if self.category != "no_answer" and not self.gold:
            raise ValueError("非 no_answer 题必须至少一条 gold")
        return self


class EvalDatasetPayload(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str = ""
    items: list[EvalItemPayload] = Field(min_length=1, max_length=500)

    @model_validator(mode="after")
    def _unique_items(self) -> "EvalDatasetPayload":
        ids = [item.id for item in self.items]
        if len(set(ids)) != len(ids):
            raise ValueError("item id 必须唯一")
        return self


class EvalRunConfig(BaseModel):
    recall_k: int = Field(30, ge=1, le=200)
    rerank_top_n: int = Field(6, ge=1, le=50)
    relevance_threshold: float = Field(0.3, ge=0.0, le=1.0)
    rewrite_enabled: bool = True
    rerank_model: str | None = None


class EvalDataset(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    name: str
    description: str = ""
    payload: EvalDatasetPayload
    item_count: int = 0
    category_counts: dict[str, int] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)


class EvalRun(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    dataset_id: UUID
    mode: EvalMode = EvalMode.RETRIEVAL
    status: EvalRunStatus = EvalRunStatus.QUEUED
    configs: list[EvalRunConfig] = Field(default_factory=list)
    progress_done: int = 0
    progress_total: int = 0
    metrics: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None
    created_at: datetime = Field(default_factory=_now)
    started_at: datetime | None = None
    finished_at: datetime | None = None


class EvalRunItem(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    run_id: UUID
    config_index: int
    question_id: str
    question: str = ""
    category: str
    item_status: EvalItemStatus
    resolution_source: ResolutionSource
    relocated: bool = False
    error: str | None = None
    best_rank: int | None = None
    recall: dict[str, Any] = Field(default_factory=dict)
    ndcg: float | None = None
    retrieved: list[dict] = Field(default_factory=list)
    gold_matched: list[dict] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)
    durations: dict[str, float] = Field(default_factory=dict)
    diagnostics: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=_now)


class ChunkContextItem(BaseModel):
    """引用预览中的单个 chunk（聚焦块或它的邻居）。"""

    chunk_id: UUID
    chunk_index: int
    heading_path: str | None = None
    content: str
    is_focus: bool = False


class ChunkContext(BaseModel):
    """引用预览：聚焦 chunk 的位置信息 + 上下文窗口。"""

    chunk_id: UUID
    document_id: UUID
    doc_title: str
    heading_path: str | None = None
    chunk_index: int
    chunk_total: int
    radius: int
    items: list[ChunkContextItem]
