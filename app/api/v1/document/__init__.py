from fastapi import APIRouter

from .document import router

document_router = APIRouter()
document_router.include_router(router, tags=["文档模块"])

__all__ = ["document_router"]
