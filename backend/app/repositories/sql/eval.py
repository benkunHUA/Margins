"""评估仓储的 SQL 实现（数据集 / 运行 / 明细）。"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.domain.entities import (
    Citation,
    EvalDataset,
    EvalDatasetPayload,
    EvalRun,
    EvalRunConfig,
    EvalRunItem,
    Page,
)
from app.domain.enums import EvalItemStatus, EvalMode, EvalRunStatus, ResolutionSource
from app.repositories.base import (
    EvalDatasetRepository,
    EvalRunItemRepository,
    EvalRunRepository,
)
from app.repositories.sql.models import EvalDatasetRow, EvalRunItemRow, EvalRunRow


def _json(value) -> str:
    return json.dumps(value, ensure_ascii=False)


class EvalDatasetSqlRepository(EvalDatasetRepository):
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._sf = session_factory

    async def create(self, dataset: EvalDataset) -> EvalDataset:
        async with self._sf() as session:
            session.add(
                EvalDatasetRow(
                    id=str(dataset.id),
                    name=dataset.name,
                    description=dataset.description,
                    payload_json=_json(dataset.payload.model_dump(mode="json")),
                    item_count=dataset.item_count,
                    category_counts_json=_json(dataset.category_counts),
                    created_at=dataset.created_at,
                    updated_at=dataset.updated_at,
                )
            )
            await session.commit()
        return dataset

    async def get(self, dataset_id: UUID) -> EvalDataset | None:
        async with self._sf() as session:
            row = await session.get(EvalDatasetRow, str(dataset_id))
            return _dataset_entity(row) if row else None

    async def get_by_name(self, name: str) -> EvalDataset | None:
        async with self._sf() as session:
            row = (
                await session.execute(
                    select(EvalDatasetRow).where(EvalDatasetRow.name == name)
                )
            ).scalar_one_or_none()
            return _dataset_entity(row) if row else None

    async def list_all(self) -> list[EvalDataset]:
        async with self._sf() as session:
            rows = (
                await session.execute(
                    select(EvalDatasetRow).order_by(EvalDatasetRow.created_at.desc())
                )
            ).scalars().all()
            return [_dataset_entity(row) for row in rows]

    async def delete(self, dataset_id: UUID) -> None:
        async with self._sf() as session:
            row = await session.get(EvalDatasetRow, str(dataset_id))
            if row is not None:
                await session.delete(row)
                await session.commit()


def _dataset_entity(row: EvalDatasetRow) -> EvalDataset:
    return EvalDataset(
        id=UUID(row.id),
        name=row.name,
        description=row.description,
        payload=EvalDatasetPayload.model_validate(json.loads(row.payload_json)),
        item_count=row.item_count,
        category_counts=json.loads(row.category_counts_json),
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


class EvalRunSqlRepository(EvalRunRepository):
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._sf = session_factory

    async def create(self, run: EvalRun) -> EvalRun:
        async with self._sf() as session:
            session.add(_run_row(run))
            await session.commit()
        return run

    async def update(self, run: EvalRun) -> EvalRun:
        async with self._sf() as session:
            row = await session.get(EvalRunRow, str(run.id))
            if row is not None:
                row.status = run.status.value
                row.configs_json = _json([c.model_dump(mode="json") for c in run.configs])
                row.progress_done = run.progress_done
                row.progress_total = run.progress_total
                row.metrics_json = _json(run.metrics)
                row.error = run.error
                row.started_at = run.started_at
                row.finished_at = run.finished_at
                await session.commit()
        return run

    async def get(self, run_id: UUID) -> EvalRun | None:
        async with self._sf() as session:
            row = await session.get(EvalRunRow, str(run_id))
            return _run_entity(row) if row else None

    async def list(self, *, page: int, page_size: int) -> Page[EvalRun]:
        async with self._sf() as session:
            total = (
                await session.execute(select(func.count()).select_from(EvalRunRow))
            ).scalar_one()
            rows = (
                await session.execute(
                    select(EvalRunRow)
                    .order_by(EvalRunRow.created_at.desc())
                    .offset((page - 1) * page_size)
                    .limit(page_size)
                )
            ).scalars().all()
            return Page(
                items=[_run_entity(row) for row in rows],
                total=total,
                page=page,
                page_size=page_size,
            )

    async def get_running(self) -> EvalRun | None:
        async with self._sf() as session:
            row = (
                await session.execute(
                    select(EvalRunRow)
                    .where(EvalRunRow.status.in_(["queued", "running"]))
                    .order_by(EvalRunRow.created_at.desc())
                    .limit(1)
                )
            ).scalar_one_or_none()
            return _run_entity(row) if row else None

    async def mark_active_failed(self, error: str) -> int:
        async with self._sf() as session:
            result = await session.execute(
                update(EvalRunRow)
                .where(EvalRunRow.status.in_(["queued", "running"]))
                .values(status="failed", error=error, finished_at=datetime.now(UTC))
            )
            await session.commit()
            return result.rowcount or 0


def _run_row(run: EvalRun) -> EvalRunRow:
    return EvalRunRow(
        id=str(run.id),
        dataset_id=str(run.dataset_id),
        mode=run.mode.value,
        status=run.status.value,
        configs_json=_json([c.model_dump(mode="json") for c in run.configs]),
        progress_done=run.progress_done,
        progress_total=run.progress_total,
        metrics_json=_json(run.metrics),
        error=run.error,
        created_at=run.created_at,
        started_at=run.started_at,
        finished_at=run.finished_at,
    )


def _run_entity(row: EvalRunRow) -> EvalRun:
    return EvalRun(
        id=UUID(row.id),
        dataset_id=UUID(row.dataset_id),
        mode=EvalMode(row.mode),
        status=EvalRunStatus(row.status),
        configs=[EvalRunConfig.model_validate(c) for c in json.loads(row.configs_json)],
        progress_done=row.progress_done,
        progress_total=row.progress_total,
        metrics=json.loads(row.metrics_json),
        error=row.error,
        created_at=row.created_at,
        started_at=row.started_at,
        finished_at=row.finished_at,
    )


class EvalRunItemSqlRepository(EvalRunItemRepository):
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._sf = session_factory

    async def add_many(self, items) -> None:
        async with self._sf() as session:
            session.add_all([_item_row(item) for item in items])
            await session.commit()

    async def list(
        self,
        *,
        run_id: UUID,
        page: int,
        page_size: int,
        config_index: int | None = None,
        item_status: EvalItemStatus | None = None,
        relocated: bool | None = None,
    ) -> Page[EvalRunItem]:
        async with self._sf() as session:
            stmt = select(EvalRunItemRow).where(EvalRunItemRow.run_id == str(run_id))
            count_stmt = select(func.count()).select_from(EvalRunItemRow).where(
                EvalRunItemRow.run_id == str(run_id)
            )
            if config_index is not None:
                stmt = stmt.where(EvalRunItemRow.config_index == config_index)
                count_stmt = count_stmt.where(EvalRunItemRow.config_index == config_index)
            if item_status is not None:
                stmt = stmt.where(EvalRunItemRow.item_status == item_status.value)
                count_stmt = count_stmt.where(
                    EvalRunItemRow.item_status == item_status.value
                )
            if relocated is not None:
                stmt = stmt.where(EvalRunItemRow.relocated == relocated)
                count_stmt = count_stmt.where(EvalRunItemRow.relocated == relocated)
            total = (await session.execute(count_stmt)).scalar_one()
            rows = (
                await session.execute(
                    stmt.order_by(EvalRunItemRow.created_at.desc())
                    .offset((page - 1) * page_size)
                    .limit(page_size)
                )
            ).scalars().all()
            return Page(
                items=[_item_entity(row) for row in rows],
                total=total,
                page=page,
                page_size=page_size,
            )


def _item_row(item: EvalRunItem) -> EvalRunItemRow:
    return EvalRunItemRow(
        id=str(item.id),
        run_id=str(item.run_id),
        config_index=item.config_index,
        question_id=item.question_id,
        category=item.category,
        item_status=item.item_status.value,
        resolution_source=item.resolution_source.value,
        relocated=item.relocated,
        error=item.error,
        best_rank=item.best_rank,
        recall_json=_json(item.recall),
        ndcg=item.ndcg,
        retrieved_json=_json(item.retrieved),
        gold_matched_json=_json(item.gold_matched),
        citations_json=_json([c.model_dump(mode="json") for c in item.citations]),
        durations_json=_json(item.durations),
        created_at=item.created_at,
    )


def _item_entity(row: EvalRunItemRow) -> EvalRunItem:
    return EvalRunItem(
        id=UUID(row.id),
        run_id=UUID(row.run_id),
        config_index=row.config_index,
        question_id=row.question_id,
        category=row.category,
        item_status=EvalItemStatus(row.item_status),
        resolution_source=ResolutionSource(row.resolution_source),
        relocated=row.relocated,
        error=row.error,
        best_rank=row.best_rank,
        recall=json.loads(row.recall_json),
        ndcg=row.ndcg,
        retrieved=json.loads(row.retrieved_json),
        gold_matched=json.loads(row.gold_matched_json),
        citations=[Citation.model_validate(c) for c in json.loads(row.citations_json)],
        durations=json.loads(row.durations_json),
        created_at=row.created_at,
    )
