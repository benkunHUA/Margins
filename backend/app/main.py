"""FastAPI 应用入口。

按详细设计采用组合根（ServiceContainer）在 lifespan 中装配依赖，
路由仅通过 Depends 获取服务，不直接感知具体实现。
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.errors import register_exception_handlers
from app.api.routers import documents, health, sessions
from app.core.config import Settings
from app.core.container import ServiceContainer
from app.core.logging import setup_logging


def create_app(
    settings: Settings | None = None,
    container: ServiceContainer | None = None,
) -> FastAPI:
    settings = settings or Settings()
    setup_logging(settings.log_level)
    container = container or ServiceContainer(settings)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        await container.startup()
        yield
        await container.shutdown()

    app = FastAPI(title="Margins 知识库系统", version="0.1.0", lifespan=lifespan)
    app.state.container = container

    app.include_router(health.router)
    app.include_router(documents.router)
    app.include_router(sessions.router)
    register_exception_handlers(app)
    return app


app = create_app()
