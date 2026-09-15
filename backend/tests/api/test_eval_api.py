"""评估 API 测试（SQL 仓储 + fake 组件；跑批在进程内后台执行）。"""

import io
import json
import time

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.container import ServiceContainer
from app.main import create_app
from app.services.embedding import EmbeddingService
from app.services.llm import LLMClient
from app.services.reranking import Reranker

_DATASET = {
    "name": "小集",
    "description": "d",
    "items": [
        {
            "id": "q1",
            "question": "价格上限？",
            "category": "single_doc_fact",
            "gold": [{"doc_title": "a.pdf", "keywords": ["40.2"]}],
        }
    ],
}


class FakeEmbeddings(EmbeddingService):
    async def embed_query(self, text):
        return [1.0, 0.0]

    async def embed_texts(self, texts):
        return [[1.0, 0.0]] * len(texts)


class FakeLLM(LLMClient):
    async def stream(self, messages):
        yield "答案"

    async def complete(self, messages):
        return ""


class FakeReranker(Reranker):
    async def rerank(self, query, candidates, *, top_n, threshold):
        return list(candidates)[:top_n]


@pytest.fixture
def client(tmp_path):
    settings = Settings(
        _env_file=None,
        data_dir=tmp_path,
        dashscope_api_key="test-key",
        llm_api_key="test",
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


def _upload(client, name: str = "小集") -> str:
    payload = dict(_DATASET, name=name)
    resp = client.post(
        "/api/eval/datasets",
        files={
            "file": (
                "dataset.json",
                io.BytesIO(json.dumps(payload).encode()),
                "application/json",
            )
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def _wait_run(client, run_id: str, timeout: float = 5.0) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        detail = client.get(f"/api/eval/runs/{run_id}").json()
        if detail["status"] in ("succeeded", "failed"):
            return detail
        time.sleep(0.05)
    raise AssertionError("评估任务超时")


def test_dataset_crud_and_validation(client) -> None:
    dataset_id = _upload(client)
    listing = client.get("/api/eval/datasets").json()
    assert listing["total"] == 1 and listing["items"][0]["item_count"] == 1
    assert client.get(f"/api/eval/datasets/{dataset_id}").status_code == 200

    bad = client.post(
        "/api/eval/datasets",
        files={"file": ("bad.json", io.BytesIO(b'{"name": ""}'), "application/json")},
    )
    assert bad.status_code == 422

    assert client.delete(f"/api/eval/datasets/{dataset_id}").status_code == 204
    assert client.get("/api/eval/datasets").json()["total"] == 0


def test_create_run_and_read_results(client) -> None:
    dataset_id = _upload(client)
    resp = client.post(
        "/api/eval/runs",
        json={
            "dataset_id": dataset_id,
            "mode": "retrieval",
            "configs": [
                {"recall_k": 10, "rerank_top_n": 3, "relevance_threshold": 0.0}
            ],
        },
    )
    assert resp.status_code == 202, resp.text
    run_id = resp.json()["id"]

    detail = _wait_run(client, run_id)
    assert detail["status"] == "succeeded"
    assert detail["progress_done"] == detail["progress_total"] == 1
    assert detail["metrics"]["0"]["invalid"] == 1  # 库里没有 a.pdf，gold 解析失效

    page = client.get(f"/api/eval/runs/{run_id}/items").json()
    assert page["total"] == 1
    assert page["items"][0]["item_status"] == "invalid"

    empty = client.get(
        f"/api/eval/runs/{run_id}/items", params={"item_status": "hit"}
    ).json()
    assert empty["total"] == 0

    assert client.get("/api/eval/runs").json()["total"] == 1
