from fastapi import APIRouter

from .static_file import router as static_file_router
from .workspace import router

workspace_router = APIRouter()
workspace_router.include_router(router, tags=["统计中心"])
workspace_router.include_router(static_file_router, prefix="/static-file", tags=["静态文件管理模块"])

__all__ = ["workspace_router"]
