"""索引基准脚本（手工运行，不进 CI）。

用途：在换机器 / 调参 / 换后端前，先量一次 SQLite 索引（FTS5 + vec0）的实际耗时，
判断"10 万 chunk 是否还够用"。

运行：

    cd backend
    uv run python scripts/bench_index.py                    # 默认 1000 / 10000 / 50000
    uv run python scripts/bench_index.py --sizes 1000 5000  # 自定义规模

说明：
- 向量是随机生成的，只测索引与检索的**机械开销**（写入、SQL、KNN、FTS），
  不含真实 embedding API 的耗时；真实入库时间还要加上 embedding 调用。
- 每个规模跑一遍 dense / sparse / hybrid，各 50 次，输出 P50 / P95。
"""

import argparse
import asyncio
import random
import statistics
import tempfile
import time
from pathlib import Path
from uuid import uuid4

from app.index.ports import IndexChangeSet, IndexRecord
from app.index.sqlite_backend import SqliteIndexBackend
from app.repositories.sql.database import run_migrations

DIMENSION = 1024
QUERIES = 50
WORDS = [
    "回购",
    "进展",
    "公司章程",
    "注册资本",
    "违约金",
    "仲裁",
    "股东大会",
    "限售股",
    "募集资金",
    "保荐机构",
]


def _random_vector(rng: random.Random) -> list[float]:
    return [rng.random() for _ in range(DIMENSION)]


def _random_text(rng: random.Random) -> str:
    return "".join(rng.choice(WORDS) for _ in range(rng.randint(8, 20)))


async def _bench_size(size: int) -> None:
    rng = random.Random(42)
    with tempfile.TemporaryDirectory() as tmp:
        data_dir = Path(tmp)
        run_migrations(data_dir)
        backend = SqliteIndexBackend(data_dir / "margins.db", dimension=DIMENSION)
        await backend.initialize()

        records = [
            IndexRecord(
                chunk_id=uuid4(),
                document_id=uuid4(),
                content=_random_text(rng),
                embedding=_random_vector(rng),
                chunk_index=index,
                metadata={"doc_title": f"doc-{index % 100}.pdf"},
            )
            for index in range(size)
        ]

        write_t0 = time.perf_counter()
        batch = 500
        for start in range(0, len(records), batch):
            await backend.apply(IndexChangeSet(upserts=records[start : start + batch]))
        write_ms = (time.perf_counter() - write_t0) * 1000

        stats = await backend.stats()
        query_vector = _random_vector(rng)
        query_text = "回购进展"

        dense_ms: list[float] = []
        sparse_ms: list[float] = []
        hybrid_ms: list[float] = []
        for _ in range(QUERIES):
            start = time.perf_counter()
            await backend.dense.search(query_vector, k=30)
            dense_ms.append((time.perf_counter() - start) * 1000)

            start = time.perf_counter()
            await backend.sparse.search(query_text, k=30)
            sparse_ms.append((time.perf_counter() - start) * 1000)

            start = time.perf_counter()
            await backend.search_hybrid(query_text, query_vector, k=30)
            hybrid_ms.append((time.perf_counter() - start) * 1000)

        await backend.close()

    print(
        f"size={size:>6} 写入={write_ms:>9.0f}ms  "
        f"chunks/fts/vec={stats['chunks']}/{stats['fts']}/{stats['vectors']}  "
        f"dense p50/p95={statistics.median(dense_ms):.1f}/{_p95(dense_ms):.1f}ms  "
        f"sparse p50/p95={statistics.median(sparse_ms):.1f}/{_p95(sparse_ms):.1f}ms  "
        f"hybrid p50/p95={statistics.median(hybrid_ms):.1f}/{_p95(hybrid_ms):.1f}ms"
    )


def _p95(values: list[float]) -> float:
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, int(round(0.95 * (len(ordered) - 1)))))
    return ordered[index]


async def _main(sizes: list[int]) -> None:
    for size in sizes:
        await _bench_size(size)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SQLite 索引基准（FTS5 + sqlite-vec）")
    parser.add_argument(
        "--sizes",
        type=int,
        nargs="+",
        default=[1000, 10000, 50000],
        help="要测的 chunk 规模，默认 1000 10000 50000",
    )
    args = parser.parse_args()
    asyncio.run(_main(args.sizes))
