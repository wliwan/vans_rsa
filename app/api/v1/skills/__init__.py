from fastapi import APIRouter

from .skills import router

skills_router = APIRouter()
skills_router.include_router(router, tags=["技能模块"])

__all__ = ["skills_router"]
