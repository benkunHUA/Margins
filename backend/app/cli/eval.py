"""命令行评估：python -m app.cli.eval --dataset 名称 [--mode full] [--config configs.json]"""

import argparse
import asyncio
import json
from pathlib import Path

from app.core.config import Settings
from app.core.container import ServiceContainer
from app.domain.entities import EvalRunConfig
from app.domain.enums import EvalMode


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="运行黄金集评估")
    parser.add_argument("--dataset", required=True, help="黄金集名称（与导入时一致）")
    parser.add_argument("--mode", choices=["retrieval", "full"], default="retrieval")
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help='参数组 JSON 文件，内容如 [{"recall_k":30,"rerank_top_n":6}]',
    )
    return parser.parse_args()


async def _run(args: argparse.Namespace) -> int:
    settings = Settings()
    container = ServiceContainer(settings, start_worker=False)
    await container.startup()
    try:
        datasets = await container.eval_service.list_datasets()
        dataset = next((item for item in datasets if item.name == args.dataset), None)
        if dataset is None:
            print(f"未找到黄金集: {args.dataset}")
            return 1
        raw = args.config.read_text(encoding="utf-8") if args.config else "[{}]"
        configs = [EvalRunConfig.model_validate(item) for item in json.loads(raw)]
        run = await container.eval_service.create_run(
            dataset_id=dataset.id,
            mode=EvalMode(args.mode),
            configs=configs,
        )
        await container.eval_runner.run(run.id)
        final = await container.eval_service.get_run(run.id)
        print(json.dumps(final.metrics, ensure_ascii=False, indent=2))
        print(f"状态: {final.status.value} · 进度 {final.progress_done}/{final.progress_total}")
        return 0 if final.status.value == "succeeded" else 1
    finally:
        await container.shutdown()


def main() -> None:
    raise SystemExit(asyncio.run(_run(_parse_args())))


if __name__ == "__main__":
    main()
