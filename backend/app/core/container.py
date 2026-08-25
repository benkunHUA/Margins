"""组合根：装配全部依赖（详细设计 §9）。SQL 仓储为默认，测试可注入替身。"""

import asyncio
import logging
from uuid import UUID

from app.core.config import Settings
from app.repositories.memory.memory_repos import (
    InMemoryChunkRepository,
    InMemoryDocumentRepository,
    InMemoryParseJobRepository,
    InMemorySessionRepository,
)
from app.repositories.sql.chunks import ChunkSqlRepository
from app.repositories.sql.database import create_engine_and_sessionmaker, init_db
from app.repositories.sql.documents import DocumentSqlRepository
from app.repositories.sql.sessions import ParseJobSqlRepository
from app.services.chat_service import ChatService
from app.services.chunking import Chunker, MarkdownChunker
from app.services.document_service import DocumentService
from app.services.embedding import DashScopeEmbeddingService, EmbeddingService
from app.services.indexing import IndexingPipeline
from app.services.llm import LangChainLLMClient
from app.services.parsing import MineruOnlineParser, MineruParser
from app.services.rag.context_builder import ContextBuilder
from app.services.rag.hybrid_retriever import HybridRetriever
from app.services.rag.pipeline import RAGPipeline
from app.services.rag.query_rewriter import LLMQueryRewriter
from app.services.reranking import DashScopeReranker
from app.vector.base import VectorRepository
from app.vector.faiss_repo import FaissVectorRepository
from app.vector.fusion import RRFFusion
from app.vector.sparse import BM25SparseIndex
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
        parser: MineruParser | None = None,
        embeddings: EmbeddingService | None = None,
        chunker: Chunker | None = None,
        vector: VectorRepository | None = None,
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
        else:
            self.documents = InMemoryDocumentRepository()
            self.chunks = InMemoryChunkRepository()
            self.jobs = InMemoryParseJobRepository()
        self.sessions = InMemorySessionRepository()  # M2 换 SQL

        self.parse_queue: asyncio.Queue[UUID] = asyncio.Queue()
        self.parser = parser or MineruOnlineParser(settings.parser)
        self.embedding = embeddings or DashScopeEmbeddingService(settings.models)
        self.chunker = chunker or MarkdownChunker()
        self.vector = vector or FaissVectorRepository(
            settings.storage, self.embedding, settings.models.embedding_dimension
        )
        self.sparse = BM25SparseIndex()
        self.llm_client = LangChainLLMClient(settings.models)
        self.reranker = DashScopeReranker(settings.models)
        self.fusion = RRFFusion()
        self.rewriter = LLMQueryRewriter(self.llm_client, settings.retrieval)
        self.hybrid = HybridRetriever(
            self.vector, self.sparse, self.embedding, self.fusion, settings.retrieval
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
        self.indexing = IndexingPipeline(self.chunker, self.embedding, self.vector, self.chunks)
        self.worker = ParseWorker(
            self.parse_queue,
            self.parser,
            self.indexing,
            self.documents,
            self.jobs,
            settings.queue,
            settings.storage,
        )
        self.document_service = DocumentService(
            self.documents,
            self.chunks,
            self.jobs,
            self.vector,
            self.sparse,
            self.parse_queue,
            settings,
        )
        self.chat_service = ChatService(self.sessions, self.rag)

    async def startup(self) -> None:
        storage = self.settings.storage
        storage.data_dir.mkdir(parents=True, exist_ok=True)
        storage.upload_dir.mkdir(parents=True, exist_ok=True)
        storage.faiss_index_dir.mkdir(parents=True, exist_ok=True)
        storage.parsed_dir.mkdir(parents=True, exist_ok=True)
        if self._engine is not None:
            await init_db(self._engine)
        await self.vector.load()
        remaining = await self.chunks.list_all()
        await self.vector.rebuild(remaining)
        if self.start_worker:
            self._worker_task = asyncio.create_task(self.worker.run())
        logger.info("容器启动完成", extra={"extra_fields": {"data_dir": str(storage.data_dir)}})

    async def shutdown(self) -> None:
        if self._worker_task is not None:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
        await self.vector.save()
        if self._engine is not None:
            await self._engine.dispose()
        logger.info("容器关闭")
