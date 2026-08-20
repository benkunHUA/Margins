"""SSE 事件格式化。"""

import json

from app.domain.events import (
    CitationsEvent,
    DeltaEvent,
    DoneEvent,
    ErrorEvent,
    MetaEvent,
    RagEvent,
)


def format_sse(event: RagEvent) -> str:
    if isinstance(event, MetaEvent):
        name, data = "meta", {"session_id": event.session_id, "message_id": event.message_id}
    elif isinstance(event, CitationsEvent):
        name, data = "citations", {"citations": [c.model_dump() for c in event.citations]}
    elif isinstance(event, DeltaEvent):
        name, data = "delta", {"content": event.content}
    elif isinstance(event, DoneEvent):
        name, data = "done", {"message_id": event.message_id}
    elif isinstance(event, ErrorEvent):
        name, data = "error", {"code": event.code, "message": event.message}
    else:
        name, data = "message", {}
    payload = json.dumps(data, ensure_ascii=False)
    return f"event: {name}\ndata: {payload}\n\n"
