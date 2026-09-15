"""评估 API 模型。"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.domain.entities import EvalRunConfig
from app.domain.enums import EvalItemStatus, EvalMode, EvalRunStatus, ResolutionSource


class DatasetOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    description: str
    item_count: int
    category_counts: dict[str, int]
    created_at: datetime
    updated_at: datetime


class DatasetDetail(DatasetOut):
    items_preview: list[dict] = Field(default_factory=list)


class RunCreateRequest(BaseModel):
    dataset_id: UUID
    mode: EvalMode = EvalMode.RETRIEVAL
    configs: list[EvalRunConfig] = Field(min_length=1, max_length=5)


class RunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    dataset_id: UUID
    mode: EvalMode
    status: EvalRunStatus
    configs: list[EvalRunConfig]
    progress_done: int
    progress_total: int
    metrics: dict
    error: str | None = None
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None


class RunItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    config_index: int
    question_id: str
    category: str
    item_status: EvalItemStatus
    resolution_source: ResolutionSource
    relocated: bool
    error: str | None = None
    best_rank: int | None = None
    recall: dict
    ndcg: float | None = None
    retrieved: list[dict]
    gold_matched: list[str]
    citations: list
