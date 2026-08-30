"""会话 API 测试（fake embeddings + fake LLM，SSE 流式）。"""

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.container import ServiceContainer
from app.main import create_app
from app.services.embedding import EmbeddingService
from app.services.llm import LLMClient


class FakeEmbeddings(EmbeddingService):
    async def embed_query(self, text):
        return [1.0, 0.0]

    async def embed_texts(self, texts):
        return [[1.0, 0.0]] * len(texts)


class FakeLLM(LLMClient):
    async def stream(self, messages):
        for token in ["你好", "！"]:
            yield token

    async def complete(self, messages):
        return ""


@pytest.fixture
def client(tmp_path):
    settings = Settings(
        _env_file=None,
        data_dir=tmp_path,
        dashscope_api_key="test-key",
        mineru_api_token="test-token",
        llm_api_key="test-llm",
    )
    container = ServiceContainer(
        settings,
        start_worker=False,
        embeddings=FakeEmbeddings(),
        llm_client=FakeLLM(),
    )
    app = create_app(settings=settings, container=container)
    with TestClient(app) as test_client:
        yield test_client


def test_session_crud_and_ask_stream(client) -> None:
    session = client.post("/api/sessions").json()
    sid = session["id"]
    assert client.get(f"/api/sessions/{sid}").status_code == 200

    with client.stream(
        "POST",
        f"/api/sessions/{sid}/messages",
        json={"question": "你好"},
    ) as resp:
        assert resp.status_code == 200
        body = "".join(resp.iter_text())

    assert "event: meta" in body
    assert "event: citations" in body
    assert "event: delta" in body
    assert "event: done" in body

    detail = client.get(f"/api/sessions/{sid}").json()
    assert len(detail["messages"]) == 2
    assert detail["messages"][-1]["content"] == "你好！"
    assert detail["session"]["title"] == "你好"

    assert client.delete(f"/api/sessions/{sid}").status_code == 204
    assert client.get(f"/api/sessions/{sid}").status_code == 404
