"""SQLite 索引后端：FTS5（jieba 预分词）+ sqlite-vec（vec0）同库、单事务写入。

设计要点：

- **同一个库**：业务表与索引表都在 `margins.db`，用 `chunks.idx_id` 连接；
  `idx_id` 既是 `chunk_fts.rowid`，也是 `chunk_vectors.rowid`。
- **原子写入**：`apply()` 在一个 SQLite 事务里删旧、写 chunks、写 FTS、写向量，
  embedding 已在事务外算好；任一步失败整体回滚，不会出现"元数据有、索引没有"。
- **索引级过滤**：`RetrievalScope.document_ids` 下推成 SQL `IN (...)` 条件，
  不把全量数据取回内存再筛。
- **同步 sqlite3 + to_thread**：sqlite3 是阻塞 API，用 `asyncio.Lock` 串行化
  写与查询，避免多线程复用同一连接时的竞态。
- **向量维度**：`chunk_vectors` 由本模块按运行时配置创建（vec0 无法改维度），
  维度变更时给出明确报错，提示删除 data 目录重建。
- **外键**：本连接不开启 `foreign_keys`（SQLAlchemy 连接仍开启）。索引一致性由
  `IndexWriter` 保证：删文档时先删索引三表，再删 `documents`。
"""

import asyncio
import json
import re
import sqlite3
from collections.abc import Sequence
from pathlib import Path
from uuid import UUID

import jieba
import sqlite_vec

from app.domain.entities import Chunk
from app.index.ports import (
    DenseIndexPort,
    IndexBackendPort,
    IndexChangeSet,
    IndexRecord,
    RetrievalScope,
    SparseIndexPort,
)
from app.index.values import ScoredChunk

# 索引键分配：与 ChunkSqlRepository 共用同一张 index_seq
_ALLOCATE = (
    "UPDATE index_seq SET next_id = next_id + :n "
    "WHERE id = 1 RETURNING next_id - :n AS start"
)
_VEC_DDL = (
    "CREATE VIRTUAL TABLE IF NOT EXISTS chunk_vectors USING vec0("
    "embedding float[{dim}] distance_metric=cosine, document_id text partition key)"
)
_DIM_RE = re.compile(r"float\s*\[\s*(\d+)\s*\]")
_CJK_RUN_RE = re.compile(r"[\u4e00-\u9fff]+")

_VECTOR_SQL = """
SELECT c.idx_id, chunk_vectors.distance, c.id, c.document_id, c.chunk_index,
       c.content, c.heading_path, c.page, c.token_count, c.metadata_json
FROM chunk_vectors
JOIN chunks c ON c.idx_id = chunk_vectors.rowid
WHERE chunk_vectors.embedding MATCH ? AND k = ?
{scope}
ORDER BY chunk_vectors.distance
LIMIT ?
"""

# bm25() 与 MATCH 必须使用真实的 FTS 表名，因此这里不给 chunk_fts 起别名
_FTS_SQL = """
SELECT c.idx_id, bm25(chunk_fts) AS score, c.id, c.document_id, c.chunk_index,
       c.content, c.heading_path, c.page, c.token_count, c.metadata_json
FROM chunk_fts
JOIN chunks c ON c.idx_id = chunk_fts.rowid
WHERE chunk_fts MATCH ?
{scope}
ORDER BY score
LIMIT ?
"""


def _tokenize(text: str) -> list[str]:
    """写入与查询共用同一分词规则：jieba 词典词 + 中文二元组。

    只靠 jieba 会漏召回：词典把"公司章程"切成一个词，用户查"章程"就命不中。
    补一层字符二元组（bigram）即可覆盖子串查询，代价是索引体积约翻倍
    （本项目目标 ≤10 万 chunk，可接受）。纯标点 token 丢弃以减少噪声。
    """
    tokens = [
        token
        for token in (raw.strip() for raw in jieba.lcut(text))
        if token and any(char.isalnum() for char in token)
    ]
    for run in _CJK_RUN_RE.findall(text):
        if len(run) == 1:
            tokens.append(run)
            continue
        tokens.extend(run[index : index + 2] for index in range(len(run) - 1))
    # 去重：同一个词既是词典词又是二元组时只计一次，避免 tf 被重复计入
    return list(dict.fromkeys(tokens))


def _to_match_query(text: str) -> str:
    """把查询切成 FTS5 短语串：每个 token 加双引号并转义内部引号。"""
    return " ".join(f'"{token.replace(chr(34), chr(34) * 2)}"' for token in _tokenize(text))


def _normalize(vector: Sequence[float]) -> list[float]:
    norm = sum(value * value for value in vector) ** 0.5
    return list(vector) if norm == 0 else [value / norm for value in vector]


def _row_to_chunk(row: tuple) -> Chunk:
    (
        idx_id,
        _score,
        chunk_id,
        document_id,
        chunk_index,
        content,
        heading_path,
        page,
        token_count,
        metadata_json,
    ) = row
    return Chunk(
        id=UUID(chunk_id),
        document_id=UUID(document_id),
        chunk_index=chunk_index,
        content=content,
        idx_id=idx_id,
        heading_path=heading_path,
        page=page,
        token_count=token_count,
        metadata=json.loads(metadata_json or "{}"),
    )


class SqliteIndexBackend(IndexBackendPort):
    """FTS5 + vec0 的默认索引后端。"""

    def __init__(self, db_path: Path, dimension: int) -> None:
        self._path = Path(db_path)
        self._dim = dimension
        self._conn: sqlite3.Connection | None = None
        self._lock = asyncio.Lock()
        self.dense: DenseIndexPort = _SqliteDenseIndex(self)
        self.sparse: SparseIndexPort = _SqliteSparseIndex(self)

    # ----- 生命周期 -----
    async def initialize(self) -> None:
        self._conn = await asyncio.to_thread(self._open)
        await asyncio.to_thread(self._ensure_vector_table)

    def _open(self) -> sqlite3.Connection:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self._path, check_same_thread=False)
        if not hasattr(conn, "enable_load_extension"):
            raise RuntimeError(
                "当前 Python 解释器不支持 SQLite 扩展加载（sqlite-vec 无法使用）；"
                "请用 uv 管理的 Python 运行后端：uv sync --python-preference only-managed"
            )
        conn.enable_load_extension(True)
        sqlite_vec.load(conn)
        conn.enable_load_extension(False)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        return conn

    async def close(self) -> None:
        conn, self._conn = self._conn, None
        if conn is not None:
            await asyncio.to_thread(conn.close)

    def _ensure_vector_table(self) -> None:
        conn = self._require()
        row = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'chunk_vectors'"
        ).fetchone()
        if row is None:
            conn.execute(_VEC_DDL.format(dim=self._dim))
            return
        match = _DIM_RE.search(row[0] or "")
        existing = int(match.group(1)) if match else None
        if existing != self._dim:
            raise RuntimeError(
                f"向量维度不一致：索引表为 {existing}，配置为 {self._dim}。"
                "维度由 embedding 模型决定，变更后需删除 data 目录并重新上传文档。"
            )

    def _require(self) -> sqlite3.Connection:
        if self._conn is None:
            raise RuntimeError("SqliteIndexBackend 尚未 initialize()")
        return self._conn

    # ----- 写入 -----
    async def apply(self, change: IndexChangeSet) -> None:
        async with self._lock:
            await asyncio.to_thread(self._apply_sync, change)

    def _apply_sync(self, change: IndexChangeSet) -> None:
        conn = self._require()
        with conn:  # 单事务：任一步失败整体回滚
            for chunk_id in change.delete_chunk_ids:
                _delete_chunk(conn, chunk_id)
            for document_id in change.delete_documents:
                _delete_document(conn, document_id)
            if change.upserts:
                start = conn.execute(_ALLOCATE, {"n": len(change.upserts)}).fetchone()[0]
                for offset, record in enumerate(change.upserts):
                    _insert_record(conn, record, start + offset, self._dim)

    async def stats(self) -> dict:
        return await asyncio.to_thread(self._stats_sync)

    def _stats_sync(self) -> dict:
        conn = self._require()
        return {
            "chunks": conn.execute("SELECT count(*) FROM chunks").fetchone()[0],
            "fts": conn.execute("SELECT count(*) FROM chunk_fts").fetchone()[0],
            "vectors": conn.execute("SELECT count(*) FROM chunk_vectors").fetchone()[0],
        }


def _delete_chunk(conn: sqlite3.Connection, chunk_id: UUID) -> None:
    row = conn.execute("SELECT idx_id FROM chunks WHERE id = ?", (str(chunk_id),)).fetchone()
    if row is None:
        return
    idx_id = row[0]
    conn.execute("DELETE FROM chunks WHERE id = ?", (str(chunk_id),))
    conn.execute("DELETE FROM chunk_fts WHERE rowid = ?", (idx_id,))
    conn.execute("DELETE FROM chunk_vectors WHERE rowid = ?", (idx_id,))


def _delete_document(conn: sqlite3.Connection, document_id: UUID) -> None:
    rows = conn.execute(
        "SELECT idx_id FROM chunks WHERE document_id = ?", (str(document_id),)
    ).fetchall()
    for (idx_id,) in rows:
        conn.execute("DELETE FROM chunk_fts WHERE rowid = ?", (idx_id,))
        conn.execute("DELETE FROM chunk_vectors WHERE rowid = ?", (idx_id,))
    conn.execute("DELETE FROM chunks WHERE document_id = ?", (str(document_id),))


def _insert_record(
    conn: sqlite3.Connection,
    record: IndexRecord,
    idx_id: int,
    dimension: int,
) -> None:
    if len(record.embedding) != dimension:
        raise ValueError(
            f"向量维度不匹配：embedding={len(record.embedding)} 配置={dimension}"
        )
    conn.execute(
        "INSERT INTO chunks (id, document_id, chunk_index, content, idx_id, heading_path, "
        "page, token_count, metadata_json, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))",
        (
            str(record.chunk_id),
            str(record.document_id),
            record.chunk_index,
            record.content,
            idx_id,
            record.heading_path,
            record.page,
            record.token_count,
            json.dumps(record.metadata, ensure_ascii=False),
        ),
    )
    conn.execute(
        "INSERT INTO chunk_fts (rowid, tokens, chunk_id, document_id) VALUES (?, ?, ?, ?)",
        (
            idx_id,
            " ".join(_tokenize(record.content)),
            str(record.chunk_id),
            str(record.document_id),
        ),
    )
    vector = sqlite_vec.serialize_float32(_normalize(record.embedding))
    conn.execute(
        "INSERT INTO chunk_vectors (rowid, embedding, document_id) VALUES (?, ?, ?)",
        (idx_id, vector, str(record.document_id)),
    )


def _scope_clause(column: str, scope: RetrievalScope | None, params: list) -> str:
    """把检索范围下推成 SQL 过滤；参数按顺序追加到 `params`。"""
    if scope is None or scope.is_global:
        return ""
    placeholders = ",".join("?" for _ in scope.document_ids)
    params.extend(str(document_id) for document_id in scope.document_ids)
    return f"AND {column} IN ({placeholders})"


class _SqliteDenseIndex(DenseIndexPort):
    """向量路：vec0 KNN（cosine），score = 1 - distance = 余弦相似度。"""

    def __init__(self, backend: SqliteIndexBackend) -> None:
        self._backend = backend

    async def upsert(self, records: Sequence[IndexRecord]) -> None:
        await self._backend.apply(IndexChangeSet(upserts=list(records)))

    async def delete(self, chunk_ids: Sequence[UUID]) -> None:
        await self._backend.apply(IndexChangeSet(delete_chunk_ids=list(chunk_ids)))

    async def delete_by_document(self, document_id: UUID) -> None:
        await self._backend.apply(IndexChangeSet(delete_documents=[document_id]))

    async def search(
        self,
        embedding: list[float],
        k: int,
        scope: RetrievalScope | None = None,
    ) -> list[ScoredChunk]:
        async with self._backend._lock:
            return await asyncio.to_thread(self._search_sync, embedding, k, scope)

    def _search_sync(
        self,
        embedding: list[float],
        k: int,
        scope: RetrievalScope | None,
    ) -> list[ScoredChunk]:
        conn = self._backend._require()
        params: list = [sqlite_vec.serialize_float32(_normalize(embedding)), k]
        clause = _scope_clause("chunk_vectors.document_id", scope, params)
        params.append(k)
        rows = conn.execute(_VECTOR_SQL.format(scope=clause), params).fetchall()
        return [
            ScoredChunk(chunk=_row_to_chunk(row), score=1.0 - float(row[1])) for row in rows
        ]


class _SqliteSparseIndex(SparseIndexPort):
    """关键词路：FTS5 bm25（越小越相关），取负让分值与其它路同向。"""

    def __init__(self, backend: SqliteIndexBackend) -> None:
        self._backend = backend

    async def upsert(self, records: Sequence[IndexRecord]) -> None:
        await self._backend.apply(IndexChangeSet(upserts=list(records)))

    async def delete(self, chunk_ids: Sequence[UUID]) -> None:
        await self._backend.apply(IndexChangeSet(delete_chunk_ids=list(chunk_ids)))

    async def delete_by_document(self, document_id: UUID) -> None:
        await self._backend.apply(IndexChangeSet(delete_documents=[document_id]))

    async def search(
        self,
        query: str,
        k: int,
        scope: RetrievalScope | None = None,
    ) -> list[ScoredChunk]:
        async with self._backend._lock:
            return await asyncio.to_thread(self._search_sync, query, k, scope)

    def _search_sync(
        self,
        query: str,
        k: int,
        scope: RetrievalScope | None,
    ) -> list[ScoredChunk]:
        match_query = _to_match_query(query)
        if not match_query:
            return []
        conn = self._backend._require()
        params: list = [match_query]
        clause = _scope_clause("c.document_id", scope, params)
        params.append(k)
        rows = conn.execute(_FTS_SQL.format(scope=clause), params).fetchall()
        return [ScoredChunk(chunk=_row_to_chunk(row), score=-float(row[1])) for row in rows]
