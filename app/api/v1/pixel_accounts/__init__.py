from fastapi import APIRouter

from .pixel_accounts import router

pixel_accounts_router = APIRouter()
pixel_accounts_router.include_router(router, tags=["像素账户模块"])

__all__ = ["pixel_accounts_router"]