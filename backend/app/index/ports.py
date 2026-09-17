"""索引能力端口。

三层职责，互相只依赖抽象：

- `DenseIndexPort` / `SparseIndexPort`：单路检索能力（向量相似度、关键词匹配）；
- `IndexBackendPort`：后端门面，负责生命周期、原子写入 `apply`，并提供默认混合检索；
- `RetrievalScope`：检索范围（文档级过滤），由上层透传到 SQL/过滤条件。

实现方只需满足这套契约即可被 `HybridRetriever` 使用；当前实现见
`app/index/sqlite_backend.py`（FTS5 + sqlite-vec），测试替身见 `tests/index/fakes.py`。
"""

from abc import ABC, abstractmethod
from collections.abc import Sequence
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.index.values import ScoredChunk


class RetrievalScope(BaseModel):
    """检索范围；`document_ids` 为空表示全库检索。"""

    document_ids: tuple[UUID, ...] = ()

    @property
    def is_global(self) -> bool:
        return not self.document_ids


class IndexRecord(BaseModel):
    """待写入索引的一条 chunk（原文 + 向量 + 过滤/展示所需元数据）。"""

    chunk_id: UUID
    document_id: UUID
    content: str
    embedding: list[float]
    chunk_index: int = 0
    heading_path: str | None = None
    page: int | None = None
    token_count: int | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class IndexChangeSet(BaseModel):
    """一次索引变更：先删除（chunk 级 / 文档级），再写入。"""

    upserts: list[IndexRecord] = Field(default_factory=list)
    delete_chunk_ids: list[UUID] = Field(default_factory=list)
    delete_documents: list[UUID] = Field(default_factory=list)


class DenseIndexPort(ABC):
    """稠密向量检索能力。"""

    @abstractmethod
    async def upsert(self, records: Sequence[IndexRecord]) -> None: ...

    @abstractmethod
    async def delete(self, chunk_ids: Sequence[UUID]) -> None: ...

    @abstractmethod
    async def delete_by_document(self, document_id: UUID) -> None: ...

    @abstractmethod
    async def search(
        self,
        embedding: list[float],
        k: int,
        scope: RetrievalScope | None = None,
    ) -> list[ScoredChunk]: ...


class SparseIndexPort(ABC):
    """稀疏（关键词）检索能力。"""

    @abstractmethod
    async def upsert(self, records: Sequence[IndexRecord]) -> None: ...

    @abstractmethod
    async def delete(self, chunk_ids: Sequence[UUID]) -> None: ...

    @abstractmethod
    async def delete_by_document(self, document_id: UUID) -> None: ...

    @abstractmethod
    async def search(
        self,
        query: str,
        k: int,
        scope: RetrievalScope | None = None,
    ) -> list[ScoredChunk]: ...


class IndexBackendPort(ABC):
    """索引后端门面：统一写入入口与可覆写的混合检索。"""

    dense: DenseIndexPort
    sparse: SparseIndexPort

    @abstractmethod
    async def initialize(self) -> None: ...

    @abstractmethod
    async def close(self) -> None: ...

    @abstractmethod
    async def stats(self) -> dict: ...

    @abstractmethod
    async def apply(self, change: IndexChangeSet) -> None:
        """原子应用变更：要么三张表全写入，要么全部回滚。"""

    async def search_hybrid(
        self,
        query: str,
        embedding: list[float],
        k: int,
        *,
        scope: RetrievalScope | None = None,
        fusion=None,
    ) -> list[ScoredChunk]:
        """默认组合实现；后端若支持原生混合检索可覆写。"""
        dense = await self.dense.search(embedding, k, scope)
        sparse = await self.sparse.search(query, k, scope)
        if fusion is None:
            return dense + sparse
        return fusion.fuse([dense, sparse], k=60, top_n=k)
