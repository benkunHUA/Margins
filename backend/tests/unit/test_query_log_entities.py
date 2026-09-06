"""QueryLog 领域实体与异常测试。"""

from uuid import UUID, uuid4

from app.core.exceptions import QueryLogNotFoundError
from app.domain.entities import Citation, QueryLog, QueryLogStep


def test_query_log_step_json_roundtrip() -> None:
    step = QueryLogStep(
        stage="rewrite",
        label="查询改写",
        duration_ms=86.5,
        summary="rephrase",
        data={"need_rewrite": True, "rewrite_type": "rephrase", "queries": ["q1"]},
    )
    assert QueryLogStep.model_validate_json(step.model_dump_json()) == step


def test_query_log_defaults() -> None:
    log = QueryLog(session_id=uuid4(), question="q")
    assert log.status == "success"
    assert log.error is None
    assert log.answer is None
    assert log.steps == []
    assert log.citations == []
    assert isinstance(log.id, UUID)


def test_query_log_json_roundtrip_keeps_steps_and_citations() -> None:
    log = QueryLog(
        session_id=uuid4(),
        session_title="回购会话",
        question="进展？",
        steps=[QueryLogStep(stage="rewrite", label="查询改写", summary="", data={})],
        citations=[
            Citation(chunk_id=uuid4(), document_id=uuid4(), doc_title="a.pdf", snippet="s")
        ],
        answer="回答",
    )
    restored = QueryLog.model_validate_json(log.model_dump_json())
    assert restored.steps[0].stage == "rewrite"
    assert restored.citations[0].doc_title == "a.pdf"
    assert restored.answer == "回答"


def test_query_log_not_found_error_is_404() -> None:
    err = QueryLogNotFoundError("不存在")
    assert err.status_code == 404
    assert err.code == "QUERY_LOG_NOT_FOUND"
