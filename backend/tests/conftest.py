"""pytest 公共夹具。"""

import pytest

from app.core.config import Settings
from app.core.container import ServiceContainer


@pytest.fixture
def settings() -> Settings:
    return Settings(_env_file=None)


@pytest.fixture
def container(settings: Settings) -> ServiceContainer:
    return ServiceContainer(settings)
