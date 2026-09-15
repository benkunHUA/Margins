"""SQLAlchemy ORM 模型（仅仓储内部可见，对外只暴露领域实体）。"""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class DocumentRow(Base):
    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    filename: Mapped[str] = mapped_column(String(255))
    file_type: Mapped[str] = mapped_column(String(16))
    file_size: Mapped[int] = mapped_column(Integer)
    file_path: Mapped[str] = mapped_column(String(1024))
    parse_mode: Mapped[str] = mapped_column(String(16), default="mineru")
    markdown_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="pending")
    parse_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    extra: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime)
    updated_at: Mapped[datetime] = mapped_column(DateTime)


class ChunkRow(Base):
    __tablename__ = "chunks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    document_id: Mapped[str] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), index=True
    )
    chunk_index: Mapped[int] = mapped_column(Integer)
    content: Mapped[str] = mapped_column(Text)
    faiss_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    heading_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    token_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    metadata_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class ParseJobRow(Base):
    __tablename__ = "parse_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    document_id: Mapped[str] = mapped_column(String(36), index=True)
    status: Mapped[str] = mapped_column(String(16), default="queued")
    attempt: Mapped[int] = mapped_column(Integer, default=0)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    queued_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class SessionRow(Base):
    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    title: Mapped[str] = mapped_column(String(255), default="新会话")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class MessageRow(Base):
    __tablename__ = "messages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    session_id: Mapped[str] = mapped_column(
        ForeignKey("sessions.id", ondelete="CASCADE"), index=True
    )
    role: Mapped[str] = mapped_column(String(16))
    content: Mapped[str] = mapped_column(Text)
    citations: Mapped[str] = mapped_column(Text, default="[]")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class QueryLogRow(Base):
    __tablename__ = "query_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    session_id: Mapped[str] = mapped_column(String(36), index=True)
    session_title: Mapped[str] = mapped_column(String(255), default="")
    question: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16), default="success")
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    total_ms: Mapped[int] = mapped_column(Integer, default=0)
    answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    steps_json: Mapped[str] = mapped_column(Text, default="[]")
    citations_json: Mapped[str] = mapped_column(Text, default="[]")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class FaissSeqRow(Base):
    __tablename__ = "faiss_seq"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    next_id: Mapped[int] = mapped_column(Integer, default=0)


class EvalDatasetRow(Base):
    __tablename__ = "eval_datasets"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    description: Mapped[str] = mapped_column(Text, default="")
    payload_json: Mapped[str] = mapped_column(Text)
    item_count: Mapped[int] = mapped_column(Integer, default=0)
    category_counts_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime)
    updated_at: Mapped[datetime] = mapped_column(DateTime)


class EvalRunRow(Base):
    __tablename__ = "eval_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    dataset_id: Mapped[str] = mapped_column(
        ForeignKey("eval_datasets.id", ondelete="CASCADE"), index=True
    )
    mode: Mapped[str] = mapped_column(String(16), default="retrieval")
    status: Mapped[str] = mapped_column(String(16), default="queued", index=True)
    configs_json: Mapped[str] = mapped_column(Text, default="[]")
    progress_done: Mapped[int] = mapped_column(Integer, default=0)
    progress_total: Mapped[int] = mapped_column(Integer, default=0)
    metrics_json: Mapped[str] = mapped_column(Text, default="{}")
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class EvalRunItemRow(Base):
    __tablename__ = "eval_run_items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    run_id: Mapped[str] = mapped_column(
        ForeignKey("eval_runs.id", ondelete="CASCADE"), index=True
    )
    config_index: Mapped[int] = mapped_column(Integer)
    question_id: Mapped[str] = mapped_column(String(64))
    question: Mapped[str] = mapped_column(Text, default="")
    category: Mapped[str] = mapped_column(String(32))
    item_status: Mapped[str] = mapped_column(String(16), index=True)
    resolution_source: Mapped[str] = mapped_column(String(16), default="invalid")
    relocated: Mapped[bool] = mapped_column(Boolean, default=False)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    best_rank: Mapped[int | None] = mapped_column(Integer, nullable=True)
    recall_json: Mapped[str] = mapped_column(Text, default="{}")
    ndcg: Mapped[float | None] = mapped_column(Float, nullable=True)
    retrieved_json: Mapped[str] = mapped_column(Text, default="[]")
    gold_matched_json: Mapped[str] = mapped_column(Text, default="[]")
    citations_json: Mapped[str] = mapped_column(Text, default="[]")
    durations_json: Mapped[str] = mapped_column(Text, default="{}")
    diagnostics_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime)
