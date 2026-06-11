from fastapi import APIRouter

from .workspace import router

workspace_router = APIRouter()
workspace_router.include_router(router, tags=["统计中心"])

__all__ = ["workspace_router"]
