"""SSE 事件格式化测试。"""

import json
from uuid import uuid4

from app.api.schemas.chat import format_sse
from app.domain.entities import Citation
from app.domain.events import CitationsEvent


def test_citations_event_serializes_uuid_as_string() -> None:
    event = CitationsEvent(
        citations=[
            Citation(
                chunk_id=uuid4(),
                document_id=uuid4(),
                doc_title="合同.pdf",
                snippet="违约金 10%",
            )
        ]
    )
    text = format_sse(event)
    assert "event: citations" in text
    data = json.loads(text.split("\n\n", 1)[0].split("data: ", 1)[1])
    citation = data["citations"][0]
    assert isinstance(citation["chunk_id"], str)
    assert isinstance(citation["document_id"], str)
