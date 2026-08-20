"""全局常量。"""

from app.domain.enums import DocumentStatus

# 允许上传的文件类型（MinerU 在线解析支持）
SUPPORTED_FILE_TYPES: set[str] = {"pdf", "docx", "md", "txt"}

# 单文件大小上限（字节）
MAX_FILE_SIZE_BYTES: int = 100 * 1024 * 1024

# 默认分块参数
DEFAULT_CHUNK_TOKEN_SIZE: int = 600
DEFAULT_CHUNK_OVERLAP: int = 80

# 会话历史默认条数（与 RetrievalConfig.history_limit 保持一致）
DEFAULT_HISTORY_LIMIT: int = 6

# 初始化会话标题截断长度
SESSION_TITLE_MAX_CHARS: int = 20

# 状态机合法迁移（pending → parsing → ready | failed）
VALID_DOCUMENT_TRANSITIONS: dict[DocumentStatus, set[DocumentStatus]] = {
    DocumentStatus.PENDING: {DocumentStatus.PARSING},
    DocumentStatus.PARSING: {DocumentStatus.READY, DocumentStatus.FAILED},
    DocumentStatus.READY: {DocumentStatus.PENDING},  # 重解析
    DocumentStatus.FAILED: {DocumentStatus.PENDING},  # 手动重试
}
