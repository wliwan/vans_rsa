from fastapi import APIRouter

from .defects import router

defects_router = APIRouter()
defects_router.include_router(router, tags=["病害数据模块"])

__all__ = ["defects_router"]
