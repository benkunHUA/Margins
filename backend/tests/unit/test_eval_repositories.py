"""评估仓储测试（内存 + SQL 同套断言）。"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

from app.domain.entities import (
    EvalDataset,
    EvalDatasetPayload,
    EvalItemPayload,
    EvalRun,
    EvalRunConfig,
    EvalRunItem,
)
from app.domain.enums import EvalItemStatus, EvalRunStatus, ResolutionSource
from app.repositories.memory.memory_repos import (
    InMemoryEvalDatasetRepository,
    InMemoryEvalRunItemRepository,
    InMemoryEvalRunRepository,
)
from app.repositories.sql.database import create_engine_and_sessionmaker, init_db
from app.repositories.sql.eval import (
    EvalDatasetSqlRepository,
    EvalRunItemSqlRepository,
    EvalRunSqlRepository,
)


def _dataset(name: str = "公告集") -> EvalDataset:
    payload = EvalDatasetPayload(
        name=name,
        items=[
            EvalItemPayload(
                id="q1",
                question="q",
                category="single_doc_fact",
                gold=[{"doc_title": "a.pdf", "keywords": ["k"]}],
            )
        ],
    )
    return EvalDataset(
        name=name,
        payload=payload,
        item_count=1,
        category_counts={"single_doc_fact": 1},
    )


def _run(dataset_id) -> EvalRun:
    return EvalRun(dataset_id=dataset_id, configs=[EvalRunConfig()], progress_total=1)


def _item(run_id) -> EvalRunItem:
    return EvalRunItem(
        run_id=run_id,
        config_index=0,
        question_id="q1",
        category="single_doc_fact",
        item_status=EvalItemStatus.HIT,
        resolution_source=ResolutionSource.KEYWORDS,
        relocated=True,
        best_rank=2,
        recall={"recall@5": True, "recall@10": True},
        retrieved=[{"rank": 1, "chunk_id": str(uuid4())}],
    )


async def _assert_repositories(datasets, runs, items) -> None:
    ds = await datasets.create(_dataset())
    assert (await datasets.get(ds.id)).name == "公告集"
    assert (await datasets.get_by_name("公告集")).id == ds.id
    assert (await datasets.list_all())[0].item_count == 1

    run = await runs.create(_run(ds.id))
    assert (await runs.get(run.id)).status == EvalRunStatus.QUEUED
    run.status = EvalRunStatus.RUNNING
    run.progress_done = 1
    await runs.update(run)
    assert (await runs.get(run.id)).progress_done == 1
    assert (await runs.list(page=1, page_size=10)).total == 1

    await items.add_many([_item(run.id)])
    page = await items.list(run_id=run.id, page=1, page_size=10)
    assert page.total == 1 and page.items[0].relocated is True
    page = await items.list(
        run_id=run.id,
        page=1,
        page_size=10,
        item_status=EvalItemStatus.HIT,
        relocated=True,
    )
    assert page.total == 1
    page = await items.list(
        run_id=run.id,
        page=1,
        page_size=10,
        item_status=EvalItemStatus.MISS,
    )
    assert page.total == 0

    await runs.mark_active_failed("服务重启中断")
    assert (await runs.get(run.id)).status == EvalRunStatus.FAILED

    await datasets.delete(ds.id)
    assert await datasets.get(ds.id) is None


async def test_memory_eval_repositories() -> None:
    await _assert_repositories(
        InMemoryEvalDatasetRepository(),
        InMemoryEvalRunRepository(),
        InMemoryEvalRunItemRepository(),
    )


async def test_sql_eval_repositories(tmp_path) -> None:
    engine, session_factory = create_engine_and_sessionmaker(tmp_path)
    await init_db(engine)
    try:
        await _assert_repositories(
            EvalDatasetSqlRepository(session_factory),
            EvalRunSqlRepository(session_factory),
            EvalRunItemSqlRepository(session_factory),
        )
    finally:
        await engine.dispose()


async def test_sql_repository_normalizes_legacy_gold_matched(tmp_path) -> None:
    """早期 run 的 gold_matched 是字符串数组，读取时应归一化为结构化明细。"""
    import json

    from sqlalchemy import insert

    from app.repositories.sql.models import (
        EvalDatasetRow,
        EvalRunItemRow,
        EvalRunRow,
    )

    engine, session_factory = create_engine_and_sessionmaker(tmp_path)
    await init_db(engine)
    item_id = str(uuid4())
    run_id = str(uuid4())
    dataset_id = str(uuid4())
    try:
        async with session_factory() as session:
            session.add(
                EvalDatasetRow(
                    id=dataset_id,
                    name="legacy",
                    description="",
                    payload_json=json.dumps(
                        {
                            "name": "legacy",
                            "description": "",
                            "items": [
                                {
                                    "id": "q1",
                                    "question": "q",
                                    "category": "single_doc_fact",
                                    "gold": [{"doc_title": "a.pdf", "keywords": ["k"]}],
                                }
                            ],
                        },
                        ensure_ascii=False,
                    ),
                    item_count=1,
                    category_counts_json="{}",
                    created_at=datetime.now(UTC),
                    updated_at=datetime.now(UTC),
                )
            )
            session.add(
                EvalRunRow(
                    id=run_id,
                    dataset_id=dataset_id,
                    mode="retrieval",
                    status="succeeded",
                    configs_json="[]",
                    progress_done=1,
                    progress_total=1,
                    metrics_json="{}",
                    created_at=datetime.now(UTC),
                )
            )
            await session.commit()
            await session.execute(
                insert(EvalRunItemRow).values(
                    id=item_id,
                    run_id=run_id,
                    config_index=0,
                    question_id="q1",
                    question="q",
                    category="single_doc_fact",
                    item_status="miss",
                    resolution_source="keywords",
                    relocated=True,
                    gold_matched_json='["legacy-chunk-id"]',
                    created_at=datetime.now(UTC),
                )
            )
            await session.commit()

        page = await EvalRunItemSqlRepository(session_factory).list(
            run_id=UUID(run_id), page=1, page_size=10
        )
        assert page.items[0].gold_matched[0]["chunk_id"] == "legacy-chunk-id"
    finally:
        await engine.dispose()
