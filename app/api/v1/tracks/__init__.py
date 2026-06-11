from fastapi import APIRouter

from .tracks import router

tracks_router = APIRouter()
tracks_router.include_router(router, tags=["轨迹点数据模块"])

__all__ = ["tracks_router"]
