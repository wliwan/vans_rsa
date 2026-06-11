from fastapi import APIRouter

from .report import router

report_router = APIRouter()
report_router.include_router(router, tags=["报告生成"])

__all__ = ["report_router"]
