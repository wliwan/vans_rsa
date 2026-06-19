from fastapi import APIRouter

from .i18n import router

i18n_router = APIRouter()
i18n_router.include_router(router, tags=["国际化管理模块"])

__all__ = ["i18n_router"]
