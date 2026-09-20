"""Chunk 相关接口（引用上下文预览）。"""

from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.api.dependencies import get_document_service
from app.domain.entities import ChunkContext
from app.services.document_service import DocumentService

router = APIRouter(prefix="/api/chunks", tags=["chunks"])


@router.get("/{chunk_id}/context", response_model=ChunkContext)
async def get_chunk_context(
    chunk_id: UUID,
    radius: int = Query(1, ge=0, le=5),
    service: DocumentService = Depends(get_document_service),
) -> ChunkContext:
    return await service.get_chunk_context(chunk_id, radius=radius)
