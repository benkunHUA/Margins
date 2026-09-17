"""端口值对象语义测试。"""

from uuid import uuid4

from app.index.ports import IndexChangeSet, IndexRecord, RetrievalScope


def test_scope_is_global_when_empty() -> None:
    assert RetrievalScope().is_global is True
    assert RetrievalScope(document_ids=(uuid4(),)).is_global is False


def test_index_change_set_defaults_are_empty() -> None:
    change = IndexChangeSet()
    assert change.upserts == [] and change.delete_chunk_ids == []
    assert change.delete_documents == []


def test_index_record_requires_embedding() -> None:
    record = IndexRecord(
        chunk_id=uuid4(),
        document_id=uuid4(),
        content="内容",
        embedding=[1.0, 0.0],
        metadata={"doc_title": "a.pdf"},
    )
    assert record.embedding == [1.0, 0.0]
