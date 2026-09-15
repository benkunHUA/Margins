"""评估领域服务：数据集导入校验、任务创建与互斥、明细查询。"""

import json
from uuid import UUID

from app.core.exceptions import AppError
from app.domain.entities import EvalDataset, EvalDatasetPayload, EvalRun, Page
from app.repositories.base import (
    EvalDatasetRepository,
    EvalRunItemRepository,
    EvalRunRepository,
)


class EvalBusyError(AppError):
    code = "EVAL_BUSY"
    status_code = 409


class EvalDatasetInvalidError(AppError):
    code = "EVAL_DATASET_INVALID"
    status_code = 422


class EvalNotFoundError(AppError):
    code = "EVAL_NOT_FOUND"
    status_code = 404


class EvalService:
    def __init__(
        self,
        datasets: EvalDatasetRepository,
        runs: EvalRunRepository,
        items: EvalRunItemRepository,
    ) -> None:
        self._datasets = datasets
        self._runs = runs
        self._items = items

    async def import_dataset(self, raw: bytes) -> EvalDataset:
        try:
            payload = EvalDatasetPayload.model_validate(json.loads(raw))
        except Exception as exc:  # noqa: BLE001 - 统一转 422
            raise EvalDatasetInvalidError(f"黄金集校验失败: {exc}") from exc
        if await self._datasets.get_by_name(payload.name):
            raise EvalDatasetInvalidError(f"同名数据集已存在: {payload.name}")
        counts: dict[str, int] = {}
        for item in payload.items:
            counts[item.category] = counts.get(item.category, 0) + 1
        dataset = EvalDataset(
            name=payload.name,
            description=payload.description,
            payload=payload,
            item_count=len(payload.items),
            category_counts=counts,
        )
        return await self._datasets.create(dataset)

    async def list_datasets(self) -> list[EvalDataset]:
        return await self._datasets.list_all()

    async def get_dataset(self, dataset_id: UUID) -> EvalDataset:
        dataset = await self._datasets.get(dataset_id)
        if dataset is None:
            raise EvalNotFoundError(f"数据集不存在: {dataset_id}")
        return dataset

    async def delete_dataset(self, dataset_id: UUID) -> None:
        running = await self._runs.get_running()
        if running is not None and running.dataset_id == dataset_id:
            raise EvalBusyError("该数据集正在评估，无法删除")
        await self._datasets.delete(dataset_id)

    async def create_run(self, *, dataset_id: UUID, mode, configs: list) -> EvalRun:
        await self.get_dataset(dataset_id)
        if await self._runs.get_running() is not None:
            raise EvalBusyError("已有评估任务在运行")
        return await self._runs.create(
            EvalRun(dataset_id=dataset_id, mode=mode, configs=configs)
        )

    async def mark_stale_failed(self) -> None:
        await self._runs.mark_active_failed("服务重启中断")

    async def list_runs(self, *, page: int, page_size: int) -> Page[EvalRun]:
        return await self._runs.list(page=page, page_size=page_size)

    async def get_run(self, run_id: UUID) -> EvalRun:
        run = await self._runs.get(run_id)
        if run is None:
            raise EvalNotFoundError(f"评估任务不存在: {run_id}")
        return run

    async def list_run_items(self, *, run_id: UUID, **filters) -> Page:
        await self.get_run(run_id)
        return await self._items.list(run_id=run_id, **filters)
