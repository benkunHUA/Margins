"""集成冒烟测试（真实 API key，pytest -m integration）。"""

import pytest

pytestmark = pytest.mark.integration
