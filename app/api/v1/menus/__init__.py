from fastapi import APIRouter

from .menus import router
from .menu_i18n import router as i18n_router

menus_router = APIRouter()
menus_router.include_router(router, tags=["菜单模块"])
menus_router.include_router(i18n_router, prefix="/i18n", tags=["菜单国际化模块"])

__all__ = ["menus_router"]