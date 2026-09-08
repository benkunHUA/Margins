"""Chunk.faiss_id 与 faiss_seq 结构测试。"""

from uuid import uuid4

from app.domain.entities import Chunk


def test_chunk_faiss_id_defaults_to_none() -> None:
    chunk = Chunk(document_id=uuid4(), chunk_index=0, content="x")
    assert chunk.faiss_id is None
