"""Chunk 上下文接口测试（SQL 仓储 + 临时数据目录，worker 不启动）。"""

import asyncio
from pathlib import Path
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.container import ServiceContainer
from app.domain.entities import Chunk, Document
from app.main import create_app

DOC_ID = UUID("22222222-2222-4222-8222-222222222222")
DOC_TITLE = "a.pdf"


@pytest.fixture
def ctx(tmp_path):
    settings = Settings(
        _env_file=None,
        data_dir=tmp_path,
        dashscope_api_key="test-key",
        mineru_api_token="test-token",
    )
    container = ServiceContainer(settings, start_worker=False)
    app = create_app(settings=settings, container=container)
    with TestClient(app) as client:
        yield client, container


def _seed(container, count: int = 5) -> list[Chunk]:
    """造 count 个 chunk（chunk_index 0..count-1），返回按顺序的列表。"""
    asyncio.run(
        container.documents.create(
            Document(
                id=DOC_ID,
                filename=DOC_TITLE,
                file_type="pdf",
                file_size=1,
                file_path=Path("a.pdf"),
            )
        )
    )
    chunks = [
        Chunk(
            id=UUID(f"11111111-1111-4111-8111-{index:012d}"),
            document_id=DOC_ID,
            chunk_index=index,
            content=f"## 第 {index} 块\n\n正文 {index}",
            heading_path=f"章节 {index}",
        )
        for index in range(count)
    ]
    asyncio.run(container.chunks.add_many(chunks))
    return chunks


def test_context_returns_focus_with_neighbours(ctx) -> None:
    client, container = ctx
    chunks = _seed(container)

    resp = client.get(f"/api/chunks/{chunks[2].id}/context")

    assert resp.status_code == 200
    body = resp.json()
    assert body["doc_title"] == DOC_TITLE
    assert body["heading_path"] == "章节 2"
    assert body["chunk_index"] == 2
    assert body["chunk_total"] == 5
    assert body["radius"] == 1
    assert [item["chunk_index"] for item in body["items"]] == [1, 2, 3]
    assert [item["is_focus"] for item in body["items"]] == [False, True, False]
    assert body["items"][1]["content"].endswith("正文 2")


def test_context_at_first_chunk_has_no_leading_neighbour(ctx) -> None:
    client, container = ctx
    chunks = _seed(container)

    body = client.get(f"/api/chunks/{chunks[0].id}/context").json()

    assert [item["chunk_index"] for item in body["items"]] == [0, 1]
    assert body["items"][0]["is_focus"] is True


def test_context_at_last_chunk_has_no_trailing_neighbour(ctx) -> None:
    client, container = ctx
    chunks = _seed(container)

    body = client.get(f"/api/chunks/{chunks[4].id}/context").json()

    assert [item["chunk_index"] for item in body["items"]] == [3, 4]
    assert body["items"][-1]["is_focus"] is True


def test_radius_zero_returns_only_focus(ctx) -> None:
    client, container = ctx
    chunks = _seed(container)

    body = client.get(f"/api/chunks/{chunks[2].id}/context", params={"radius": 0}).json()

    assert [item["chunk_index"] for item in body["items"]] == [2]
    assert body["items"][0]["is_focus"] is True


def test_radius_over_limit_is_rejected(ctx) -> None:
    client, container = ctx
    chunks = _seed(container)

    resp = client.get(f"/api/chunks/{chunks[0].id}/context", params={"radius": 6})

    assert resp.status_code == 422


def test_unknown_chunk_returns_chunk_not_found(ctx) -> None:
    client, _ = ctx

    resp = client.get(f"/api/chunks/{UUID(int=1234)}/context")

    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "CHUNK_NOT_FOUND"
