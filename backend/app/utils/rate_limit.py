"""异步令牌桶限速器。"""

import asyncio
import time


class AsyncTokenBucket:
    """按速率补充令牌的异步限速器。"""

    def __init__(self, rate: float, capacity: float) -> None:
        if rate <= 0 or capacity <= 0:
            raise ValueError("rate 与 capacity 必须为正数")
        self._rate = rate
        self._capacity = capacity
        self._tokens = capacity
        self._updated_at = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self, tokens: float = 1.0) -> None:
        async with self._lock:
            while True:
                now = time.monotonic()
                elapsed = now - self._updated_at
                self._tokens = min(self._capacity, self._tokens + elapsed * self._rate)
                self._updated_at = now
                if self._tokens >= tokens:
                    self._tokens -= tokens
                    return
                await asyncio.sleep((tokens - self._tokens) / self._rate)
