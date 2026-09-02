"""应用配置。

采用 pydantic-settings 读取 .env；环境变量沿用概要设计 §11 的扁平命名
（如 DASHSCOPE_API_KEY、RECALL_K），通过 validation_alias 映射。
运行时通过属性暴露分组的配置对象（storage / models / retrieval / parser / queue）。
"""

from pathlib import Path

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class StorageConfig(BaseModel):
    data_dir: Path = Path("./data")

    @property
    def upload_dir(self) -> Path:
        return self.data_dir / "uploads"

    @property
    def faiss_index_dir(self) -> Path:
        return self.data_dir / "faiss_index"

    @property
    def parsed_dir(self) -> Path:
        return self.data_dir / "parsed"

    @property
    def db_path(self) -> Path:
        return self.data_dir / "margins.db"


class ModelConfig(BaseModel):
    dashscope_api_key: str = ""
    embedding_model: str = "text-embedding-v4"
    embedding_dimension: int = 1024
    rerank_model: str = "qwen3-rerank"
    llm_base_url: str = "https://api.deepseek.com"
    llm_api_key: str = ""
    llm_model: str = "deepseek-chat"
    rerank_instruct: str = ""


class RetrievalConfig(BaseModel):
    recall_k: int = 30
    rerank_top_n: int = 6
    relevance_threshold: float = 0.3
    max_citations: int = 5
    max_chunks_per_document: int = 3
    min_chunk_chars: int = 30
    history_limit: int = 6


class ParserConfig(BaseModel):
    mineru_api_token: str = ""
    flash_max_size_mb: int = 10
    flash_max_pages: int = 20


class QueueConfig(BaseModel):
    concurrency: int = 2
    max_retries: int = 3
    backoff_seconds: tuple[float, ...] = (1.0, 5.0, 15.0)


class RewriteConfig(BaseModel):
    enabled: bool = True
    history_limit: int = 6
    temperature: float = 0.2


class ImageSummaryConfig(BaseModel):
    """图片文字总结（M5-1）：MinerU 取图 → qwen3.8-max VLM 总结 → 入库。"""

    api_key: str = ""
    enabled: bool = True
    model: str = "qwen3.8-max"
    max_images: int = 10
    min_bytes: int = 5120
    temperature: float = 0.2
    thinking: bool = False
    max_tokens: int = 800


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # ----- 百炼 -----
    dashscope_api_key: str = Field("", validation_alias="DASHSCOPE_API_KEY")
    embedding_model: str = Field("text-embedding-v4", validation_alias="EMBEDDING_MODEL")
    embedding_dimension: int = Field(1024, validation_alias="EMBEDDING_DIMENSION")
    rerank_model: str = Field("qwen3-rerank", validation_alias="RERANK_MODEL")

    # ----- MinerU -----
    mineru_api_token: str = Field("", validation_alias="MINERU_API_TOKEN")
    flash_max_size_mb: int = Field(10, validation_alias="FLASH_MAX_SIZE_MB")
    flash_max_pages: int = Field(20, validation_alias="FLASH_MAX_PAGES")

    # ----- LLM -----
    llm_base_url: str = Field("https://api.deepseek.com", validation_alias="LLM_BASE_URL")
    llm_api_key: str = Field("", validation_alias="LLM_API_KEY")
    llm_model: str = Field("deepseek-chat", validation_alias="LLM_MODEL")
    rerank_instruct: str = Field("", validation_alias="RERANK_INSTRUCT")

    # ----- 存储 -----
    data_dir: Path = Field(Path("./data"), validation_alias="DATA_DIR")

    # ----- 检索 -----
    recall_k: int = Field(30, validation_alias="RECALL_K")
    rerank_top_n: int = Field(6, validation_alias="RERANK_TOP_N")
    relevance_threshold: float = Field(0.3, validation_alias="RELEVANCE_THRESHOLD")
    max_citations: int = Field(5, validation_alias="MAX_CITATIONS")
    max_chunks_per_document: int = Field(3, validation_alias="MAX_CHUNKS_PER_DOCUMENT")
    min_chunk_chars: int = Field(30, validation_alias="MIN_CHUNK_CHARS")
    history_limit: int = Field(6, validation_alias="HISTORY_LIMIT")

    # ----- 查询重写 -----
    rewrite_enabled: bool = Field(True, validation_alias="REWRITE_ENABLED")
    rewrite_temperature: float = Field(0.2, validation_alias="REWRITE_TEMPERATURE")

    # ----- 图片文字总结 -----
    image_summary_enabled: bool = Field(True, validation_alias="IMAGE_SUMMARY_ENABLED")
    image_summary_model: str = Field("qwen3.8-max", validation_alias="IMAGE_SUMMARY_MODEL")
    image_summary_max_images: int = Field(10, validation_alias="IMAGE_SUMMARY_MAX_IMAGES")
    image_summary_min_bytes: int = Field(5120, validation_alias="IMAGE_SUMMARY_MIN_BYTES")
    image_summary_temperature: float = Field(0.2, validation_alias="IMAGE_SUMMARY_TEMPERATURE")
    image_summary_thinking: bool = Field(False, validation_alias="IMAGE_SUMMARY_THINKING")

    # ----- 任务队列 -----
    queue_concurrency: int = Field(2, validation_alias="QUEUE__CONCURRENCY")
    queue_max_retries: int = Field(3, validation_alias="QUEUE__MAX_RETRIES")

    # ----- 日志 -----
    log_level: str = Field("INFO", validation_alias="LOG_LEVEL")

    @property
    def storage(self) -> StorageConfig:
        return StorageConfig(data_dir=self.data_dir)

    @property
    def models(self) -> ModelConfig:
        return ModelConfig(
            dashscope_api_key=self.dashscope_api_key,
            embedding_model=self.embedding_model,
            embedding_dimension=self.embedding_dimension,
            rerank_model=self.rerank_model,
            llm_base_url=self.llm_base_url,
            llm_api_key=self.llm_api_key,
            llm_model=self.llm_model,
            rerank_instruct=self.rerank_instruct,
        )

    @property
    def retrieval(self) -> RetrievalConfig:
        return RetrievalConfig(
            recall_k=self.recall_k,
            rerank_top_n=self.rerank_top_n,
            relevance_threshold=self.relevance_threshold,
            max_citations=self.max_citations,
            max_chunks_per_document=self.max_chunks_per_document,
            min_chunk_chars=self.min_chunk_chars,
            history_limit=self.history_limit,
        )

    @property
    def parser(self) -> ParserConfig:
        return ParserConfig(
            mineru_api_token=self.mineru_api_token,
            flash_max_size_mb=self.flash_max_size_mb,
            flash_max_pages=self.flash_max_pages,
        )

    @property
    def queue(self) -> QueueConfig:
        return QueueConfig(
            concurrency=self.queue_concurrency,
            max_retries=self.queue_max_retries,
        )

    @property
    def rewrite(self) -> RewriteConfig:
        return RewriteConfig(
            enabled=self.rewrite_enabled,
            history_limit=self.history_limit,
            temperature=self.rewrite_temperature,
        )

    @property
    def image_summary(self) -> ImageSummaryConfig:
        return ImageSummaryConfig(
            api_key=self.dashscope_api_key,
            enabled=self.image_summary_enabled,
            model=self.image_summary_model,
            max_images=self.image_summary_max_images,
            min_bytes=self.image_summary_min_bytes,
            temperature=self.image_summary_temperature,
            thinking=self.image_summary_thinking,
        )
