"""索引层值对象。"""

from pydantic import BaseModel

from app.domain.entities import Chunk


class ScoredChunk(BaseModel):
    """检索命中：chunk 本体 + 该路检索给出的分数（越大越相关）。"""

    chunk: Chunk
    score: float
