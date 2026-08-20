"""组合根：装配全部依赖（详细设计 §9）。"""

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
from app.services.chat_service import ChatService
from app.services.chunking import MarkdownChunker
from app.services.document_service import DocumentService
from app.services.embedding import DashScopeEmbeddingService
from app.services.indexing import IndexingPipeline
from app.services.llm import LangChainLLMClient
from app.services.parsing import MineruOnlineParser
from app.services.rag.context_builder import ContextBuilder
from app.services.rag.hybrid_retriever import HybridRetriever
from app.services.rag.pipeline import RAGPipeline
from app.services.rag.query_rewriter import LLMQueryRewriter
from app.services.reranking import DashScopeReranker
from app.vector.faiss_repo import FaissVectorRepository
from app.vector.fusion import RRFFusion
from app.vector.sparse import BM25SparseIndex
from app.workers.parse_worker import ParseWorker

logger = logging.getLogger(__name__)


class ServiceContainer:
    """依赖图根节点；测试可注入替代实现构造测试版容器。"""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

        # 仓储（骨架阶段使用内存实现；M1 切换为 SQLAlchemy 实现）
        self.documents = InMemoryDocumentRepository()
        self.chunks = InMemoryChunkRepository()
        self.sessions = InMemorySessionRepository()
        self.jobs = InMemoryParseJobRepository()

        # 队列与索引
        self.parse_queue: asyncio.Queue[UUID] = asyncio.Queue()
        self.vector = FaissVectorRepository(settings.storage)
        self.sparse = BM25SparseIndex()

        # 外部能力
        self.embedding = DashScopeEmbeddingService(settings.models)
        self.parser = MineruOnlineParser(settings.parser)
        self.chunker = MarkdownChunker()
        self.llm_client = LangChainLLMClient(settings.models)
        self.reranker = DashScopeReranker(settings.models)

        # 检索管线
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

        # 入库与任务
        self.indexing = IndexingPipeline(self.chunker, self.embedding, self.vector, self.chunks)
        self.worker = ParseWorker(
            self.parse_queue, self.parser, self.indexing, self.documents, self.jobs, settings.queue
        )

        # 服务
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
        logger.info("容器启动完成", extra={"extra_fields": {"data_dir": str(storage.data_dir)}})

    async def shutdown(self) -> None:
        logger.info("容器关闭")
