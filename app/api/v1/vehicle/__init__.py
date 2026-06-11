from fastapi import APIRouter

from .vehicle import router

vehicle_router = APIRouter()
vehicle_router.include_router(router, tags=["车辆状态检测模块"])

__all__ = ["vehicle_router"]
