"""QueryLog 仓储测试（内存 + SQL 同套断言）。"""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.domain.entities import QueryLog, QueryLogStep
from app.repositories.memory.memory_repos import InMemoryQueryLogRepository
from app.repositories.sql.database import create_engine_and_sessionmaker, init_db
from app.repositories.sql.query_logs import QueryLogSqlRepository


def _log(
    *,
    question: str = "回购进展？",
    status: str = "success",
    offset: int = 0,
    answer: str | None = None,
    session_id=None,
) -> QueryLog:
    return QueryLog(
        session_id=session_id or uuid4(),
        session_title="回购会话",
        question=question,
        status=status,
        answer=answer,
        total_ms=1234.5,
        steps=[
            QueryLogStep(
                stage="rewrite",
                label="查询改写",
                duration_ms=86,
                summary="rephrase",
                data={"queries": ["安旭生物回购进展"]},
            )
        ],
        created_at=datetime.now(UTC) - timedelta(seconds=offset),
    )


async def _assert_roundtrip(repo) -> None:
    created = await repo.create(_log())
    got = await repo.get(created.id)
    assert got is not None
    assert got.question == created.question
    assert got.steps[0].stage == "rewrite"
    assert got.total_ms == pytest.approx(1234.5, abs=1)  # SQL 列按整型毫秒存储
    assert await repo.get(uuid4()) is None


async def _assert_filters_and_pagination(repo) -> None:
    sid = uuid4()
    await repo.create(_log(question="寒武纪注册地址", offset=3))
    await repo.create(_log(session_id=sid, offset=2))
    await repo.create(_log(status="failed", question="寒武纪股东", offset=1))
    await repo.create(_log(session_id=sid, answer="回购方案实施期限为…", offset=0))

    page = await repo.list(page=1, page_size=10, q="寒武纪")
    assert page.total == 2

    page = await repo.list(page=1, page_size=10, session_id=sid)
    assert page.total == 2

    page = await repo.list(page=1, page_size=10, status="failed")
    assert page.total == 1
    assert page.items[0].status == "failed"

    page = await repo.list(page=1, page_size=2)
    assert page.total == 4
    assert len(page.items) == 2
    assert page.items[0].created_at >= page.items[1].created_at  # 新→旧


async def test_memory_repository_roundtrip() -> None:
    await _assert_roundtrip(InMemoryQueryLogRepository())


async def test_memory_repository_filters_and_pagination() -> None:
    await _assert_filters_and_pagination(InMemoryQueryLogRepository())


@pytest.fixture
async def sql_repo(tmp_path):
    engine, session_factory = create_engine_and_sessionmaker(tmp_path)
    await init_db(engine)
    yield QueryLogSqlRepository(session_factory)
    await engine.dispose()


async def test_sql_repository_roundtrip(sql_repo) -> None:
    await _assert_roundtrip(sql_repo)


async def test_sql_repository_filters_and_pagination(sql_repo) -> None:
    await _assert_filters_and_pagination(sql_repo)
