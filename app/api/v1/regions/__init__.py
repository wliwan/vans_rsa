from fastapi import APIRouter

from .boundary import router as boundary_router
from .regions import router
from .road_network import router as road_network_router

regions_router = APIRouter()
regions_router.include_router(router, tags=["全球国家及行政区管理模块"])
regions_router.include_router(boundary_router, prefix="/region-boundary", tags=["行政区边界文件管理模块"])
regions_router.include_router(road_network_router, prefix="/road-network", tags=["路网文件管理模块"])

__all__ = ["regions_router"]
