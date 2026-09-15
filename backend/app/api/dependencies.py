"""路由依赖：从应用状态获取容器与服务。"""

from fastapi import Depends, Request

from app.core.container import ServiceContainer
from app.services.chat_service import ChatService
from app.services.document_service import DocumentService
from app.services.eval.runner import EvalRunner
from app.services.eval.service import EvalService
from app.services.query_log_service import QueryLogService


def get_container(request: Request) -> ServiceContainer:
    return request.app.state.container


def get_document_service(container: ServiceContainer = Depends(get_container)) -> DocumentService:
    return container.document_service


def get_chat_service(container: ServiceContainer = Depends(get_container)) -> ChatService:
    return container.chat_service


def get_query_log_service(
    container: ServiceContainer = Depends(get_container),
) -> QueryLogService:
    return container.log_service


def get_eval_service(
    container: ServiceContainer = Depends(get_container),
) -> EvalService:
    return container.eval_service


def get_eval_runner(
    container: ServiceContainer = Depends(get_container),
) -> EvalRunner:
    return container.eval_runner
