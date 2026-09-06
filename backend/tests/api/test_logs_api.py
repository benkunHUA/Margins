"""查询链路日志 API 测试（fake LLM/embedding/rerank，走真实 RAG 管线）。"""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.container import ServiceContainer
from app.main import create_app
from app.services.embedding import EmbeddingService
from app.services.llm import LLMClient
from app.services.reranking import Reranker


class FakeEmbeddings(EmbeddingService):
    async def embed_query(self, text):
        return [1.0, 0.0]

    async def embed_texts(self, texts):
        return [[1.0, 0.0]] * len(texts)


class FakeLLM(LLMClient):
    async def stream(self, messages):
        for token in ["根据", "[1]", "回答"]:
            yield token

    async def complete(self, messages):
        return ""


class FakeReranker(Reranker):
    async def rerank(self, query, candidates, *, top_n, threshold, trace=None):
        return list(candidates)[:top_n]


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
        reranker=FakeReranker(),
    )
    app = create_app(settings=settings, container=container)
    with TestClient(app) as test_client:
        yield test_client


def _ask(client, question: str = "违约金多少？") -> None:
    session = client.post("/api/sessions").json()
    with client.stream(
        "POST",
        f"/api/sessions/{session['id']}/messages",
        json={"question": question},
    ) as resp:
        assert resp.status_code == 200
        for _ in resp.iter_text():
            pass


def test_logs_list_summary_and_detail(client) -> None:
    _ask(client)

    listing = client.get("/api/logs").json()
    assert listing["total"] == 1
    item = listing["items"][0]
    assert item["question"] == "违约金多少？"
    assert item["status"] == "success"
    assert item["citation_count"] >= 0
    assert "steps" not in item  # 列表不返回大体积步骤

    detail = client.get(f"/api/logs/{item['id']}").json()
    stages = [step["stage"] for step in detail["steps"]]
    assert stages == ["rewrite", "hybrid", "rerank", "context", "llm"]
    assert detail["answer"] == "根据[1]回答"
    assert detail["session_title"] == "违约金多少？"


def test_logs_list_filters(client) -> None:
    _ask(client, "回购进展？")
    _ask(client, "寒武纪地址？")

    page = client.get("/api/logs", params={"q": "寒武纪"}).json()
    assert page["total"] == 1
    assert page["items"][0]["question"] == "寒武纪地址？"

    page = client.get("/api/logs", params={"status": "success"}).json()
    assert page["total"] == 2

    page = client.get("/api/logs", params={"status": "failed"}).json()
    assert page["total"] == 0


def test_logs_detail_404_for_unknown(client) -> None:
    _ask(client)
    assert client.get(f"/api/logs/{uuid4()}").status_code == 404
