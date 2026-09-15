"""评估接口。"""

from uuid import UUID

from fastapi import APIRouter, Depends, File, Query, UploadFile
from fastapi.responses import Response

from app.api.dependencies import get_eval_runner, get_eval_service
from app.api.schemas.eval import (
    DatasetDetail,
    DatasetOut,
    RunCreateRequest,
    RunItemOut,
    RunOut,
)
from app.domain.entities import Page
from app.domain.enums import EvalItemStatus
from app.services.eval.runner import EvalRunner
from app.services.eval.service import EvalService

router = APIRouter(prefix="/api/eval", tags=["eval"])


def _preview(dataset) -> list[dict]:
    return [
        {"id": item.id, "question": item.question, "category": item.category}
        for item in dataset.payload.items[:5]
    ]


@router.post("/datasets", status_code=201, response_model=DatasetOut)
async def upload_dataset(
    file: UploadFile = File(...),
    service: EvalService = Depends(get_eval_service),
) -> DatasetOut:
    return DatasetOut.model_validate(await service.import_dataset(await file.read()))


@router.get("/datasets", response_model=Page[DatasetOut])
async def list_datasets(
    service: EvalService = Depends(get_eval_service),
) -> Page[DatasetOut]:
    datasets = await service.list_datasets()
    return Page(
        items=[DatasetOut.model_validate(dataset) for dataset in datasets],
        total=len(datasets),
        page=1,
        page_size=max(len(datasets), 1),
    )


@router.get("/datasets/{dataset_id}", response_model=DatasetDetail)
async def get_dataset(
    dataset_id: UUID,
    service: EvalService = Depends(get_eval_service),
) -> DatasetDetail:
    dataset = await service.get_dataset(dataset_id)
    return DatasetDetail(
        **DatasetOut.model_validate(dataset).model_dump(),
        items_preview=_preview(dataset),
    )


@router.delete("/datasets/{dataset_id}", status_code=204)
async def delete_dataset(
    dataset_id: UUID,
    service: EvalService = Depends(get_eval_service),
) -> Response:
    await service.delete_dataset(dataset_id)
    return Response(status_code=204)


@router.post("/runs", status_code=202, response_model=RunOut)
async def create_run(
    body: RunCreateRequest,
    service: EvalService = Depends(get_eval_service),
    runner: EvalRunner = Depends(get_eval_runner),
) -> RunOut:
    run = await service.create_run(
        dataset_id=body.dataset_id,
        mode=body.mode,
        configs=body.configs,
    )
    await runner.start(run.id)
    return RunOut.model_validate(run)


@router.get("/runs", response_model=Page[RunOut])
async def list_runs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    service: EvalService = Depends(get_eval_service),
) -> Page[RunOut]:
    result = await service.list_runs(page=page, page_size=page_size)
    return Page(
        items=[RunOut.model_validate(run) for run in result.items],
        total=result.total,
        page=result.page,
        page_size=result.page_size,
    )


@router.get("/runs/{run_id}", response_model=RunOut)
async def get_run(
    run_id: UUID,
    service: EvalService = Depends(get_eval_service),
) -> RunOut:
    return RunOut.model_validate(await service.get_run(run_id))


@router.get("/runs/{run_id}/items", response_model=Page[RunItemOut])
async def list_run_items(
    run_id: UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    config_index: int | None = Query(None, ge=0),
    item_status: EvalItemStatus | None = Query(None),
    relocated: bool | None = Query(None),
    service: EvalService = Depends(get_eval_service),
) -> Page[RunItemOut]:
    result = await service.list_run_items(
        run_id=run_id,
        page=page,
        page_size=page_size,
        config_index=config_index,
        item_status=item_status,
        relocated=relocated,
    )
    return Page(
        items=[RunItemOut.model_validate(item) for item in result.items],
        total=result.total,
        page=result.page,
        page_size=result.page_size,
    )
