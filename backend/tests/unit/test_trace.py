"""Trace 采集对象测试。"""

from datetime import UTC, datetime
from uuid import uuid4

from app.domain.entities import Citation
from app.services.rag.trace import Trace


def test_trace_records_steps_in_order() -> None:
    trace = Trace(session_id=uuid4(), session_title="会话", question="进展？")
    trace.record(
        stage="rewrite",
        label="查询改写",
        duration_ms=86.5,
        summary="rephrase",
        data={"queries": ["q"]},
    )
    trace.record(
        stage="llm",
        label="LLM 生成",
        duration_ms=2100,
        summary="38 chunks",
        data={"stream_chunks": 38},
    )

    steps = trace.steps()
    assert [step.stage for step in steps] == ["rewrite", "llm"]
    assert steps[0].duration_ms == 86.5
    assert steps[0].data["queries"] == ["q"]


def test_trace_builds_query_log() -> None:
    trace = Trace(session_id=uuid4(), session_title="回购会话", question="进展？")
    trace.record(
        stage="rewrite",
        label="查询改写",
        duration_ms=86,
        summary="rephrase",
        data={"queries": ["q"]},
    )
    log = trace.build(
        status="success",
        error=None,
        answer="回答内容",
        citations=[
            Citation(chunk_id=uuid4(), document_id=uuid4(), doc_title="a.pdf", snippet="s")
        ],
        total_ms=3200.0,
        created_at=datetime.now(UTC),
    )
    assert log.session_title == "回购会话"
    assert log.question == "进展？"
    assert log.status == "success"
    assert log.answer == "回答内容"
    assert log.total_ms == 3200.0
    assert len(log.steps) == 1
    assert len(log.citations) == 1


def test_trace_failed_build_keeps_error() -> None:
    trace = Trace(session_id=uuid4(), session_title="会话", question="q")
    log = trace.build(
        status="failed",
        error="embedding 失败",
        answer=None,
        citations=[],
        total_ms=120.0,
        created_at=datetime.now(UTC),
    )
    assert log.status == "failed"
    assert log.error == "embedding 失败"
    assert log.answer is None
