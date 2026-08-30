"""重排序服务：阿里云百炼 qwen3-rerank（dashscope.TextReRank.call，可注入替身）。"""

import asyncio
from abc import ABC, abstractmethod
from collections.abc import Sequence

import dashscope

from app.core.config import ModelConfig
from app.vector.base import ScoredChunk


class Reranker(ABC):
    @abstractmethod
    async def rerank(
        self,
        query: str,
        candidates: Sequence[ScoredChunk],
        *,
        top_n: int,
        threshold: float,
    ) -> list[ScoredChunk]: ...


class DashScopeReranker(Reranker):
    def __init__(self, config: ModelConfig, call=None) -> None:
        self._config = config
        self._call = call or dashscope.TextReRank.call

    async def rerank(
        self,
        query: str,
        candidates: Sequence[ScoredChunk],
        *,
        top_n: int,
        threshold: float,
    ) -> list[ScoredChunk]:
        if not candidates:
            return []

        def _do() -> list[tuple[int, float]]:
            kwargs = {}
            if self._config.rerank_instruct:
                kwargs["instruct"] = self._config.rerank_instruct
            response = self._call(
                model=self._config.rerank_model,
                query=query,
                documents=[item.chunk.content for item in candidates],
                top_n=top_n,
                api_key=self._config.dashscope_api_key,
                return_documents=False,
                **kwargs,
            )
            return _extract_results(response)

        scored = await asyncio.to_thread(_do)
        result: list[ScoredChunk] = []
        for index, score in scored:
            if score >= threshold and 0 <= index < len(candidates):
                item = candidates[index]
                result.append(ScoredChunk(chunk=item.chunk, score=score))
        return result


def _extract_results(response) -> list[tuple[int, float]]:
    output = getattr(response, "output", None)
    if output is None and isinstance(response, dict):
        output = response.get("output")
    results = getattr(output, "results", None)
    if results is None and isinstance(output, dict):
        results = output.get("results")
    if not results:
        return []
    out: list[tuple[int, float]] = []
    for item in results:
        index = getattr(item, "index", None)
        score = getattr(item, "relevance_score", None)
        if isinstance(item, dict):
            index = item.get("index", index)
            score = item.get("relevance_score", score)
        if index is not None and score is not None:
            out.append((int(index), float(score)))
    return out
