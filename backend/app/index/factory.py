"""索引后端工厂：本期只实现 sqlite，未来新增 lancedb / qdrant 时在此加分发。"""

from app.core.config import Settings
from app.index.ports import IndexBackendPort
from app.index.sqlite_backend import SqliteIndexBackend


def create_index_backend(settings: Settings) -> IndexBackendPort:
    backend = settings.index.backend
    if backend != "sqlite":
        raise ValueError(f"未知索引后端: {backend}（当前仅支持 sqlite）")
    return SqliteIndexBackend(
        settings.storage.db_path,
        dimension=settings.models.embedding_dimension,
    )
