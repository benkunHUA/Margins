"""领域异常定义。

API 层通过 app/api/errors.py 将异常映射为 HTTP 状态码与统一错误响应体。
"""


class AppError(Exception):
    """业务异常基类。"""

    code = "APP_ERROR"
    status_code = 500

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class DocumentNotFoundError(AppError):
    code = "DOCUMENT_NOT_FOUND"
    status_code = 404


class SessionNotFoundError(AppError):
    code = "SESSION_NOT_FOUND"
    status_code = 404


class InvalidFileTypeError(AppError):
    code = "INVALID_FILE_TYPE"
    status_code = 422


class FileTooLargeError(AppError):
    code = "FILE_TOO_LARGE"
    status_code = 422


class ParseFailedError(AppError):
    code = "PARSE_FAILED"
    status_code = 409


class EmbeddingError(AppError):
    code = "EMBEDDING_ERROR"
    status_code = 502


class RerankError(AppError):
    code = "RERANK_ERROR"
    status_code = 502


class LLMError(AppError):
    code = "LLM_ERROR"
    status_code = 502


class IndexCorruptError(AppError):
    code = "INDEX_CORRUPT"
    status_code = 500


class NotImplementedStageError(AppError):
    """骨架占位：对应里程碑尚未实现。"""

    code = "NOT_IMPLEMENTED"
    status_code = 501
