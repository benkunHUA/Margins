"""领域枚举。"""

from enum import StrEnum


class DocumentStatus(StrEnum):
    PENDING = "pending"
    PARSING = "parsing"
    READY = "ready"
    FAILED = "failed"


class ParseJobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class MessageRole(StrEnum):
    USER = "user"
    ASSISTANT = "assistant"


class ParseMode(StrEnum):
    MINERU = "mineru"
    PLAIN_TEXT = "plain_text"


class EvalMode(StrEnum):
    RETRIEVAL = "retrieval"
    FULL = "full"


class EvalRunStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class EvalItemStatus(StrEnum):
    HIT = "hit"
    MISS = "miss"
    INVALID = "invalid"
    NO_ANSWER = "no_answer"
    ERROR = "error"


class ResolutionSource(StrEnum):
    CHUNK_ID = "chunk_id"
    SNIPPET = "snippet"
    KEYWORDS = "keywords"
    INVALID = "invalid"
