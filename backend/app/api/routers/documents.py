"""文档管理接口。"""

from pathlib import Path
from uuid import UUID

import anyio
from fastapi import APIRouter, Depends, File, Query, UploadFile
from fastapi.responses import Response

from app.api.dependencies import get_document_service
from app.api.schemas.documents import ChunkOut, DocumentDetail, DocumentOut, UploadResult
from app.domain.entities import Page
from app.domain.enums import DocumentStatus
from app.services.document_service import DocumentService

router = APIRouter(prefix="/api/documents", tags=["documents"])


@router.post("", status_code=202, response_model=list[UploadResult])
async def upload_documents(
    files: list[UploadFile] = File(...),
    service: DocumentService = Depends(get_document_service),
) -> list[UploadResult]:
    results = await service.upload(files)
    return [UploadResult(**item) for item in results]


@router.get("", response_model=Page[DocumentOut])
async def list_documents(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: DocumentStatus | None = None,
    q: str | None = None,
    service: DocumentService = Depends(get_document_service),
) -> Page[DocumentOut]:
    result = await service.list(page=page, page_size=page_size, status=status, q=q)
    return Page(
        items=[DocumentOut.model_validate(doc) for doc in result.items],
        total=result.total,
        page=result.page,
        page_size=result.page_size,
    )


@router.get("/{document_id}", response_model=DocumentDetail)
async def get_document(
    document_id: UUID,
    service: DocumentService = Depends(get_document_service),
) -> DocumentDetail:
    doc = await service.get(document_id)
    markdown: str | None = None
    if doc.markdown_path and Path(doc.markdown_path).is_file():
        markdown = await anyio.to_thread.run_sync(Path(doc.markdown_path).read_text, "utf-8")
    detail = DocumentDetail.model_validate(doc)
    detail.markdown = markdown
    return detail


@router.get("/{document_id}/chunks", response_model=list[ChunkOut])
async def list_document_chunks(
    document_id: UUID,
    service: DocumentService = Depends(get_document_service),
) -> list[ChunkOut]:
    chunks = await service.list_chunks(document_id)
    return [ChunkOut.model_validate(chunk) for chunk in chunks]


@router.delete("/{document_id}", status_code=204)
async def delete_document(
    document_id: UUID,
    service: DocumentService = Depends(get_document_service),
) -> Response:
    await service.delete(document_id)
    return Response(status_code=204)


@router.post("/{document_id}/reparse", status_code=202)
async def reparse_document(
    document_id: UUID,
    service: DocumentService = Depends(get_document_service),
) -> dict:
    return await service.reparse(document_id)
