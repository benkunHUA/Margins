"""解析任务 Worker（进程内 asyncio 队列，M1 落地）。"""

from app.core.config import QueueConfig
from app.core.exceptions import NotImplementedStageError
from app.repositories.base import DocumentRepository, ParseJobRepository
from app.services.indexing import IndexingPipeline
from app.services.parsing import MineruParser


class ParseWorker:
    def __init__(
        self,
        queue,
        parser: MineruParser,
        indexing: IndexingPipeline,
        documents: DocumentRepository,
        jobs: ParseJobRepository,
        config: QueueConfig,
    ) -> None:
        self._queue = queue
        self._parser = parser
        self._indexing = indexing
        self._documents = documents
        self._jobs = jobs
        self._config = config

    async def run(self) -> None:
        """M1 落地：状态机 pending→parsing→ready|failed，指数退避重试。"""
        raise NotImplementedStageError("M1: 解析 worker")
