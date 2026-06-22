from fastapi import APIRouter

from .deploy import router

deploy_router = APIRouter()
deploy_router.include_router(router)
