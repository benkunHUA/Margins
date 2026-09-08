"""文档 API 测试（SQL 仓储 + 临时数据目录，worker 不启动）。"""

import asyncio
import io
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.container import ServiceContainer
from app.domain.entities import Chunk
from app.main import create_app


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
    with TestClient(app) as test_client:
        yield test_client, container


def _upload(client, name: str = "a.md", content: bytes = b"# hello") -> str:
    resp = client.post(
        "/api/documents",
        files={"files": (name, io.BytesIO(content), "text/markdown")},
    )
    assert resp.status_code == 202
    return resp.json()[0]["document_id"]


def test_upload_and_list(ctx) -> None:
    client, _ = ctx
    _upload(client)
    listed = client.get("/api/documents").json()
    assert listed["total"] == 1
    assert listed["items"][0]["filename"] == "a.md"
    assert listed["items"][0]["status"] == "pending"


def test_get_missing_document_returns_404(ctx) -> None:
    client, _ = ctx
    assert client.get(f"/api/documents/{uuid4()}").status_code == 404


def test_delete_document(ctx) -> None:
    client, _ = ctx
    doc_id = _upload(client)
    assert client.delete(f"/api/documents/{doc_id}").status_code == 204
    assert client.get("/api/documents").json()["total"] == 0


def test_reparse_enqueues_new_job(ctx) -> None:
    client, _ = ctx
    doc_id = _upload(client)
    resp = client.post(f"/api/documents/{doc_id}/reparse")
    assert resp.status_code == 202
    assert resp.json()["status"] == "queued"


def test_chunks_endpoint_lists_chunks(ctx) -> None:
    client, container = ctx
    doc_id = _upload(client)

    asyncio.run(
        container.chunks.add_many(
            [
                Chunk(
                    id=UUID("11111111-1111-4111-8111-111111111111"),
                    document_id=UUID(doc_id),
                    chunk_index=0,
                    content="# 第一段",
                    heading_path="标题",
                    token_count=4,
                )
            ]
        )
    )

    resp = client.get(f"/api/documents/{doc_id}/chunks")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["chunk_index"] == 0
    assert body[0]["content"] == "# 第一段"
    assert body[0]["heading_path"] == "标题"


def _upload_with_mode(client, name: str, mode: str | None = None) -> dict:
    data = {"parse_mode": mode} if mode is not None else None
    resp = client.post(
        "/api/documents",
        data=data,
        files={"files": (name, io.BytesIO(b"x"), "application/octet-stream")},
    )
    assert resp.status_code == 202
    return resp.json()[0]


def test_upload_pdf_with_plain_text_mode(ctx) -> None:
    client, _ = ctx
    item = _upload_with_mode(client, "plain.pdf", mode="plain_text")
    assert item["parse_mode"] == "plain_text"

    listed = client.get("/api/documents").json()["items"][0]
    assert listed["parse_mode"] == "plain_text"


def test_upload_txt_always_plain_text(ctx) -> None:
    client, _ = ctx
    item = _upload_with_mode(client, "a.txt", mode="mineru")
    assert item["parse_mode"] == "plain_text"


def test_reparse_switches_parse_mode(ctx) -> None:
    client, container = ctx
    doc_id = _upload_with_mode(client, "plain.pdf", mode="plain_text")["document_id"]

    resp = client.post(f"/api/documents/{doc_id}/reparse", json={"parse_mode": "mineru"})
    assert resp.status_code == 202
    assert resp.json()["parse_mode"] == "mineru"
    assert resp.json()["status"] == "queued"

    doc = asyncio.run(container.documents.get(UUID(doc_id)))
    assert doc.parse_mode.value == "mineru"


def test_reparse_txt_ignores_mineru_request(ctx) -> None:
    client, container = ctx
    doc_id = _upload_with_mode(client, "a.txt", mode="plain_text")["document_id"]

    resp = client.post(f"/api/documents/{doc_id}/reparse", json={"parse_mode": "mineru"})
    assert resp.json()["parse_mode"] == "plain_text"


def test_upload_invalid_parse_mode_returns_422(ctx) -> None:
    client, _ = ctx
    resp = client.post(
        "/api/documents",
        data={"parse_mode": "banana"},
        files={"files": ("a.pdf", io.BytesIO(b"x"), "application/octet-stream")},
    )
    assert resp.status_code == 422
