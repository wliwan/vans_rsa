"""系统配置 API"""
from fastapi import APIRouter, Body

from app.controllers.system_config import system_config_controller
from app.schemas.base import Success

router = APIRouter()


@router.get("/download", summary="获取下载配置")
async def get_download_config():
    return Success(data=await system_config_controller.get_all())


@router.post("/download", summary="更新下载配置")
async def update_download_config(config: dict = Body(..., description="配置键值对")):
    """body: {"download_proxy": "http://...", "download_chunk_count": "4", ...}"""
    result = await system_config_controller.set_all(config)
    return Success(data=result)


@router.post("/test-proxy", summary="测试代理连通性")
async def test_proxy(proxy_url: str = Body(..., embed=True, description="代理地址")):
    """body: {"proxy_url": "http://127.0.0.1:7890"}"""
    result = await system_config_controller.test_proxy(proxy_url)
    return Success(data=result)
