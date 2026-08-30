"""健康检查。"""

from fastapi import APIRouter, Depends

from app import __version__
from app.api.dependencies import get_container
from app.core.container import ServiceContainer

router = APIRouter(prefix="/api/health", tags=["health"])


@router.get("")
async def health(container: ServiceContainer = Depends(get_container)) -> dict:
    documents = len(await container.documents.list_all())
    return {"status": "ok", "version": __version__, "documents": documents}
