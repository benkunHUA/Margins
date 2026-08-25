"""文档 API 测试（SQL 仓储 + 临时数据目录，worker 不启动）。"""

import io
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.container import ServiceContainer
from app.main import create_app


@pytest.fixture
def client(tmp_path):
    settings = Settings(
        _env_file=None,
        data_dir=tmp_path,
        dashscope_api_key="test-key",
        mineru_api_token="test-token",
    )
    container = ServiceContainer(settings, start_worker=False)
    app = create_app(settings=settings, container=container)
    with TestClient(app) as test_client:
        yield test_client


def _upload(client, name: str = "a.md", content: bytes = b"# hello") -> str:
    resp = client.post(
        "/api/documents",
        files={"files": (name, io.BytesIO(content), "text/markdown")},
    )
    assert resp.status_code == 202
    return resp.json()[0]["document_id"]


def test_upload_and_list(client) -> None:
    _upload(client)
    listed = client.get("/api/documents").json()
    assert listed["total"] == 1
    assert listed["items"][0]["filename"] == "a.md"
    assert listed["items"][0]["status"] == "pending"


def test_get_missing_document_returns_404(client) -> None:
    assert client.get(f"/api/documents/{uuid4()}").status_code == 404


def test_delete_document(client) -> None:
    doc_id = _upload(client)
    assert client.delete(f"/api/documents/{doc_id}").status_code == 204
    assert client.get("/api/documents").json()["total"] == 0


def test_reparse_enqueues_new_job(client) -> None:
    doc_id = _upload(client)
    resp = client.post(f"/api/documents/{doc_id}/reparse")
    assert resp.status_code == 202
    assert resp.json()["status"] == "queued"
