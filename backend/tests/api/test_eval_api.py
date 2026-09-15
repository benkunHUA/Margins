"""评估 API 测试（SQL 仓储 + fake 组件；跑批在进程内后台执行）。"""

import asyncio
import io
import json
import time
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.container import ServiceContainer
from app.domain.entities import (
    EvalDataset,
    EvalDatasetPayload,
    EvalItemPayload,
    EvalRun,
    EvalRunConfig,
    EvalRunItem,
)
from app.domain.enums import EvalItemStatus, ResolutionSource
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
        yield test_client, container


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
    client, _ = client
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
    client, _ = client
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


def test_run_items_serialize_structured_gold(client) -> None:
    client, container = client

    async def seed():
        payload = EvalDatasetPayload(
            name="结构化",
            items=[
                EvalItemPayload(
                    id="q1",
                    question="q",
                    category="single_doc_fact",
                    gold=[{"doc_title": "a.pdf", "keywords": ["k"]}],
                )
            ],
        )
        dataset = await container.eval_datasets.create(
            EvalDataset(name="结构化", payload=payload, item_count=1)
        )
        run = await container.eval_runs.create(
            EvalRun(dataset_id=dataset.id, configs=[EvalRunConfig()], progress_total=1)
        )
        await container.eval_items.add_many(
            [
                EvalRunItem(
                    run_id=run.id,
                    config_index=0,
                    question_id="q1",
                    question="q",
                    category="single_doc_fact",
                    item_status=EvalItemStatus.MISS,
                    resolution_source=ResolutionSource.KEYWORDS,
                    relocated=True,
                    gold_matched=[
                        {
                            "chunk_id": str(uuid4()),
                            "doc_title": "a.pdf",
                            "heading_path": "第一章",
                            "snippet": "答案原文",
                        }
                    ],
                    diagnostics={"dense_raw": 3, "dense_filtered": 3, "sparse": 0, "fused": 3},
                )
            ]
        )
        return run.id

    run_id = asyncio.run(seed())
    page = client.get(f"/api/eval/runs/{run_id}/items")
    assert page.status_code == 200, page.text
    item = page.json()["items"][0]
    assert item["gold_matched"][0]["doc_title"] == "a.pdf"
    assert item["diagnostics"]["dense_raw"] == 3
