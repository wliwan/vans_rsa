from fastapi import APIRouter

from .ai_proxy import router

ai_proxy_router = APIRouter()
ai_proxy_router.include_router(router, tags=["AI代理模块"])

__all__ = ["ai_proxy_router"]
