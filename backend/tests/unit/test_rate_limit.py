"""令牌桶限速器测试。"""

import asyncio

from app.utils.rate_limit import AsyncTokenBucket


def test_acquire_within_capacity() -> None:
    async def scenario() -> None:
        bucket = AsyncTokenBucket(rate=1000, capacity=5)
        for _ in range(5):
            await bucket.acquire()

    asyncio.run(scenario())


def test_acquire_blocks_when_empty() -> None:
    async def scenario() -> None:
        bucket = AsyncTokenBucket(rate=1000, capacity=1)
        await bucket.acquire()
        start = asyncio.get_running_loop().time()
        await asyncio.wait_for(bucket.acquire(), timeout=1.0)
        assert asyncio.get_running_loop().time() - start >= 0.0

    asyncio.run(scenario())
