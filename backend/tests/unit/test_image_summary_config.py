"""ImageSummaryConfig 读取环境变量与默认值测试。"""

from app.core.config import Settings


def test_image_summary_defaults_without_env() -> None:
    settings = Settings(_env_file=None)
    cfg = settings.image_summary
    assert cfg.enabled is True
    assert cfg.model == "qwen3.8-max"
    assert cfg.max_images == 10
    assert cfg.min_bytes == 5120
    assert cfg.temperature == 0.2
    assert cfg.thinking is False


def test_image_summary_settings_read_env(monkeypatch) -> None:
    monkeypatch.setenv("IMAGE_SUMMARY_ENABLED", "false")
    monkeypatch.setenv("IMAGE_SUMMARY_MODEL", "qwen3.8-max")
    monkeypatch.setenv("IMAGE_SUMMARY_MAX_IMAGES", "3")
    monkeypatch.setenv("IMAGE_SUMMARY_MIN_BYTES", "100")
    monkeypatch.setenv("IMAGE_SUMMARY_TEMPERATURE", "0.1")
    monkeypatch.setenv("IMAGE_SUMMARY_THINKING", "true")
    settings = Settings(_env_file=None)
    cfg = settings.image_summary
    assert cfg.enabled is False
    assert cfg.model == "qwen3.8-max"
    assert cfg.max_images == 3
    assert cfg.min_bytes == 100
    assert cfg.temperature == 0.1
    assert cfg.thinking is True
    assert cfg.api_key == settings.dashscope_api_key  # 与百炼共用 Key
