"""M1 集成冒烟：真实 MinerU + 百炼（需要 .env 密钥，pytest -m integration）。"""

import base64
import io
import time

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.container import ServiceContainer
from app.main import create_app

# 最小合法 PDF（588 字节，含 "MinerU sample" 文本）
SAMPLE_PDF_B64 = (
    "JVBERi0xLjQKMSAwIG9iago8PCAvVHlwZSAvQ2F0YWxvZyAvUGFnZXMgMiAwIFIgPj4KZW5kb2JqCjIgMCBvYmoK"
    "PDwgL1R5cGUgL1BhZ2VzIC9LaWRzIFszIDAgUl0gL0NvdW50IDEgPj4KZW5kb2JqCjMgMCBvYmoKPDwgL1R5cGUg"
    "L1BhZ2UgL1BhcmVudCAyIDAgUiAvTWVkaWFCb3ggWzAgMCA2MTIgNzkyXSAvQ29udGVudHMgNCAwIFIgL1Jlc291"
    "cmNlcyA8PCAvRm9udCA8PCAvRjEgNSAwIFIgPj4gPj4gPj4KZW5kb2JqCjQgMCBvYmoKPDwgL0xlbmd0aCA0NCA+"
    "PgpzdHJlYW0KQlQgL0YxIDI0IFRmIDcyIDcyMCBUZCAoTWluZXJVIHNhbXBsZSkgVGogRVQKZW5kc3RyZWFtCmVu"
    "ZG9iago1IDAgb2JqCjw8IC9UeXBlIC9Gb250IC9TdWJ0eXBlIC9UeXBlMSAvQmFzZUZvbnQgL0hlbHZldGljYSA+"
    "PgplbmRvYmoKeHJlZgowIDYKMDAwMDAwMDAwMCA2NTUzNSBmIAowMDAwMDAwMDA5IDAwMDAwIG4gCjAwMDAwMDAw"
    "NTggMDAwMDAgbiAKMDAwMDAwMDExNSAwMDAwMCBuIAowMDAwMDAwMjQxIDAwMDAwIG4gCjAwMDAwMDAzMzUgMDAw"
    "MDAgbiAKdHJhaWxlcgo8PCAvU2l6ZSA2IC9Sb290IDEgMCBSID4+CnN0YXJ0eHJlZgo0MDUKJSVFT0YK"
)


@pytest.mark.integration
def test_upload_parse_ready(tmp_path) -> None:
    settings = Settings(_env_file=None, data_dir=tmp_path)
    container = ServiceContainer(settings)  # 启动真实 worker
    app = create_app(settings=settings, container=container)

    with TestClient(app) as client:
        resp = client.post(
            "/api/documents",
            files={
                "files": (
                    "sample.pdf",
                    io.BytesIO(base64.b64decode(SAMPLE_PDF_B64)),
                    "application/pdf",
                )
            },
        )
        assert resp.status_code == 202
        doc_id = resp.json()[0]["document_id"]

        doc = None
        for _ in range(90):
            doc = client.get(f"/api/documents/{doc_id}").json()
            if doc["status"] in ("ready", "failed"):
                break
            time.sleep(2)

        assert doc is not None
        assert doc["status"] == "ready", f"解析失败: {doc.get('parse_error')}"
        assert doc["markdown"]
