"""系统配置 API"""
import os

from fastapi import APIRouter, Body

from app.controllers.system_config import system_config_controller
from app.schemas.base import Success, Fail
from app.log import logger
from app.settings.config import settings

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


# ═══════════════════════════════════════════
# 路网瓦片渲染样式
# ═══════════════════════════════════════════

@router.get("/road-highway-style", summary="获取路网瓦片渲染样式（颜色+线宽）")
async def get_road_highway_style():
    """返回当前生效的 highway 颜色和线宽配置"""
    import json
    from app.utils.road_network_tiler import HIGHWAY_COLORS, HIGHWAY_WEIGHT_FACTOR, _highway_colors_override, _highway_weight_override

    colors_raw = await system_config_controller.get_value("road_highway_colors", "{}")
    weights_raw = await system_config_controller.get_value("road_highway_weights", "{}")

    if isinstance(colors_raw, str):
        colors_raw = json.loads(colors_raw)
    if isinstance(weights_raw, str):
        weights_raw = json.loads(weights_raw)

    return Success(data={
        "colors": colors_raw or {k: list(v) for k, v in HIGHWAY_COLORS.items()},
        "weights": weights_raw or HIGHWAY_WEIGHT_FACTOR,
        "has_override": _highway_colors_override is not None or _highway_weight_override is not None,
    })


@router.post("/road-highway-style", summary="更新路网瓦片渲染样式")
async def update_road_highway_style(
    colors: dict = Body(None, description="颜色映射 {highway: [R,G,B]}"),
    weights: dict = Body(None, description="线宽系数 {highway: float}"),
):
    """设置 road_highway_colors 和 road_highway_weights，并立即生效到瓦片渲染器"""
    import json
    from app.utils.road_network_tiler import apply_highway_config

    if not colors and not weights:
        return Fail(code=400, msg="至少需要提供 colors 或 weights 之一")

    if colors:
        await system_config_controller.set_value("road_highway_colors", json.dumps(colors, ensure_ascii=False))
    if weights:
        await system_config_controller.set_value("road_highway_weights", json.dumps(weights, ensure_ascii=False))

    # 立即生效到瓦片渲染器
    apply_highway_config(colors=colors, weights=weights)

    # 清除瓦片磁盘缓存（样式变更后旧缓存失效）
    import shutil
    tiles_root = os.path.join(settings.BASE_DIR, "uploads", "tiles")
    if os.path.exists(tiles_root):
        shutil.rmtree(tiles_root, ignore_errors=True)
        logger.info("瓦片缓存已清除（样式变更）")

    logger.info(f"路网样式已更新: colors={'yes' if colors else 'no'} weights={'yes' if weights else 'no'}")

    return Success(data={
        "colors": colors,
        "weights": weights,
    }, msg="路网渲染样式已更新，瓦片缓存已清除，新请求将立即生效")


@router.delete("/road-highway-style", summary="重置路网瓦片渲染样式为默认")
async def reset_road_highway_style():
    """清除自定义样式，恢复默认颜色和线宽"""
    from app.utils.road_network_tiler import apply_highway_config

    await system_config_controller.set_value("road_highway_colors", "{}")
    await system_config_controller.set_value("road_highway_weights", "{}")
    apply_highway_config(colors=None, weights=None)
    logger.info("路网样式已重置为默认")
    return Success(msg="路网渲染样式已重置为默认")
