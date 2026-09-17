"""组合根：装配全部依赖（详细设计 §9）。SQL 仓储为默认，测试可注入替身。"""

import asyncio
import logging
from uuid import UUID

from app.core.config import Settings
from app.index.factory import create_index_backend
from app.index.fusion import RRFFusion
from app.index.writer import IndexWriter
from app.repositories.memory.memory_repos import (
    InMemoryChunkRepository,
    InMemoryDocumentRepository,
    InMemoryEvalDatasetRepository,
    InMemoryEvalRunItemRepository,
    InMemoryEvalRunRepository,
    InMemoryParseJobRepository,
    InMemoryQueryLogRepository,
    InMemorySessionRepository,
)
from app.repositories.sql.chunks import ChunkSqlRepository
from app.repositories.sql.database import create_engine_and_sessionmaker, run_migrations
from app.repositories.sql.documents import DocumentSqlRepository
from app.repositories.sql.eval import (
    EvalDatasetSqlRepository,
    EvalRunItemSqlRepository,
    EvalRunSqlRepository,
)
from app.repositories.sql.query_logs import QueryLogSqlRepository
from app.repositories.sql.sessions import ParseJobSqlRepository, SessionSqlRepository
from app.services.chat_service import ChatService
from app.services.chunking import Chunker, MarkdownChunker
from app.services.document_service import DocumentService
from app.services.embedding import DashScopeEmbeddingService, EmbeddingService
from app.services.eval.runner import EvalRunner
from app.services.eval.service import EvalService
from app.services.image_summarizer import DashScopeImageSummarizer, ImageSummarizer
from app.services.indexing import IndexingPipeline
from app.services.llm import LangChainLLMClient, LLMClient
from app.services.parsing import DocumentParser, MineruOnlineParser, PlainTextParser
from app.services.query_log_service import QueryLogService
from app.services.rag.context_builder import ContextBuilder
from app.services.rag.hybrid_retriever import HybridRetriever
from app.services.rag.pipeline import RAGPipeline
from app.services.rag.query_rewriter import LLMQueryRewriter
from app.services.reranking import DashScopeReranker, Reranker
from app.workers.parse_worker import ParseWorker

logger = logging.getLogger(__name__)


class ServiceContainer:
    """依赖图根节点；测试可注入替身构造测试版容器。"""

    def __init__(
        self,
        settings: Settings,
        *,
        repositories: str = "sql",
        start_worker: bool = True,
        parser: DocumentParser | None = None,
        embeddings: EmbeddingService | None = None,
        chunker: Chunker | None = None,
        index_backend=None,
        llm_client: LLMClient | None = None,
        reranker: Reranker | None = None,
        image_summarizer: ImageSummarizer | None = None,
    ) -> None:
        self.settings = settings
        self.start_worker = start_worker
        self._worker_task: asyncio.Task | None = None
        self._engine = None

        if repositories == "sql":
            self._engine, session_factory = create_engine_and_sessionmaker(
                settings.storage.data_dir
            )
            self.documents = DocumentSqlRepository(session_factory)
            self.chunks = ChunkSqlRepository(session_factory)
            self.jobs = ParseJobSqlRepository(session_factory)
            self.sessions = SessionSqlRepository(session_factory)
            self.query_logs = QueryLogSqlRepository(session_factory)
            self.eval_datasets = EvalDatasetSqlRepository(session_factory)
            self.eval_runs = EvalRunSqlRepository(session_factory)
            self.eval_items = EvalRunItemSqlRepository(session_factory)
        else:
            self.documents = InMemoryDocumentRepository()
            self.chunks = InMemoryChunkRepository()
            self.jobs = InMemoryParseJobRepository()
            self.sessions = InMemorySessionRepository()
            self.query_logs = InMemoryQueryLogRepository()
            self.eval_datasets = InMemoryEvalDatasetRepository()
            self.eval_runs = InMemoryEvalRunRepository()
            self.eval_items = InMemoryEvalRunItemRepository()

        self.parse_queue: asyncio.Queue[UUID] = asyncio.Queue()
        self.parser = parser or MineruOnlineParser(settings.parser)
        self.plain_parser = PlainTextParser()
        self.embedding = embeddings or DashScopeEmbeddingService(settings.models)
        self.chunker = chunker or MarkdownChunker()
        self.index_backend = index_backend or create_index_backend(settings)
        self.index_writer = IndexWriter(self.index_backend, self.embedding)
        self.llm_client = llm_client or LangChainLLMClient(settings.models)
        self.reranker = reranker or DashScopeReranker(settings.models)
        self.image_summarizer = image_summarizer or DashScopeImageSummarizer(
            settings.image_summary
        )
        self.fusion = RRFFusion()
        self.eval_service = EvalService(
            self.eval_datasets, self.eval_runs, self.eval_items
        )
        self.eval_runner = EvalRunner(
            datasets=self.eval_datasets,
            runs=self.eval_runs,
            items=self.eval_items,
            documents=self.documents,
            chunks=self.chunks,
            embeddings=self.embedding,
            index_backend=self.index_backend,
            fusion=self.fusion,
            reranker=self.reranker,
            llm_client=self.llm_client,
            settings=settings,
        )
        self.rewriter = LLMQueryRewriter(self.llm_client, settings.rewrite)
        self.hybrid = HybridRetriever(
            self.index_backend, self.embedding, self.fusion, settings.retrieval
        )
        self.context_builder = ContextBuilder(settings.retrieval)
        self.rag = RAGPipeline(
            self.rewriter,
            self.hybrid,
            self.reranker,
            self.context_builder,
            self.llm_client,
            settings.retrieval,
        )
        self.indexing = IndexingPipeline(self.chunker, self.index_writer)
        self.worker = ParseWorker(
            self.parse_queue,
            self.parser,
            self.indexing,
            self.documents,
            self.jobs,
            settings.queue,
            settings.storage,
            image_summarizer=self.image_summarizer,
            image_config=settings.image_summary,
            plain_parser=self.plain_parser,
        )
        self.document_service = DocumentService(
            self.documents,
            self.chunks,
            self.jobs,
            self.index_writer,
            self.parse_queue,
            settings,
        )
        self.chat_service = ChatService(
            self.sessions,
            self.rag,
            history_limit=settings.retrieval.history_limit,
            logs=self.query_logs,
        )
        self.log_service = QueryLogService(self.query_logs)

    async def startup(self) -> None:
        storage = self.settings.storage
        storage.data_dir.mkdir(parents=True, exist_ok=True)
        storage.upload_dir.mkdir(parents=True, exist_ok=True)
        storage.parsed_dir.mkdir(parents=True, exist_ok=True)
        if self._engine is not None:
            await asyncio.to_thread(run_migrations, storage.data_dir)
        await self.eval_service.mark_stale_failed()
        await self.index_backend.initialize()
        stats = await self.index_backend.stats()
        logger.info(
            "索引后端就绪",
            extra={"extra_fields": {"backend": self.settings.index.backend, **stats}},
        )
        if self.start_worker:
            self._worker_task = asyncio.create_task(self.worker.run())
        logger.info("容器启动完成", extra={"extra_fields": {"data_dir": str(storage.data_dir)}})

    async def shutdown(self) -> None:
        await self.eval_runner.shutdown()
        if self._worker_task is not None:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
        await self.index_backend.close()
        if self._engine is not None:
            await self._engine.dispose()
        logger.info("容器关闭")
