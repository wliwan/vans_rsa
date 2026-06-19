"""路网文件管理 API"""
import base64

import httpx
from fastapi import APIRouter, File, Query, Request, UploadFile
from fastapi.responses import Response

from typing import Optional

from pydantic import BaseModel, Field

from app.controllers.region import region_controller
from app.controllers.system_config import system_config_controller
from app.log import logger
from app.utils.http_utils import make_download_response
from app.schemas.base import Success, SuccessExtra
from app.schemas.regions import FilterTemplateCreate, RoadNetworkDownloadRequest

router = APIRouter()


@router.get("/status", summary="检查路网文件状态")
async def check_road_network_status(region_id: int = Query(..., description="区域ID")):
    data = await region_controller.get_road_network_status(region_id)
    return Success(data=data)


@router.post("/download", summary="从 OSM 下载路网数据")
async def download_road_network(req: RoadNetworkDownloadRequest):
    data = await region_controller.download_road_network(
        req.region_id, req.mode, req.file_type.value
    )
    return Success(data=data, msg="下载成功")


@router.post("/upload", summary="上传路网文件")
async def upload_road_network(
    region_id: int = Query(..., description="区域ID"),
    file: UploadFile = File(...),
):
    content = await file.read()
    data = await region_controller.upload_road_network(
        region_id, content, file.filename or "network.graphml"
    )
    return Success(data=data, msg="上传成功")


@router.delete("/delete", summary="删除单个路网文件")
async def delete_road_network(network_id: int = Query(..., description="路网文件ID")):
    await region_controller.delete_road_network(network_id)
    return Success(msg="Deleted Successfully")


@router.delete("/clear", summary="清除区域所有路网文件")
async def clear_road_networks(region_id: int = Query(..., description="区域ID")):
    count = await region_controller.clear_road_networks(region_id)
    return Success(data={"deleted": count}, msg=f"已清除 {count} 个文件")


@router.get("/download-file", summary="导出/下载路网文件")
async def download_road_network_file(network_id: int = Query(..., description="路网文件ID")):
    file_path, file_name, media_type = await region_controller.export_road_network(network_id)
    return make_download_response(
        path=file_path, filename=file_name, media_type=media_type)


# ── 路网工作台 ──

@router.get("/list-for-region", summary="获取区域下的路网文件列表")
async def list_networks_for_region(region_id: int = Query(..., description="区域ID")):
    data = await region_controller.get_road_network_list(region_id)
    return Success(data=data)


@router.get("/analyze", summary="路网分析（统计+GeoJSON+等级列表）")
async def analyze_network(network_id: int = Query(..., description="路网文件ID")):
    data = await region_controller.analyze_road_network(network_id)
    return Success(data=data)


class FilterRequest(BaseModel):
    network_id: int = Field(..., description="路网文件ID")
    selected_types: list = Field(..., description="选中的道路等级列表")
    save_to_region: bool = Field(False, description="是否保存到区域下")


@router.post("/filter", summary="按道路等级筛选路网")
async def filter_network(req: FilterRequest):
    data = await region_controller.filter_road_network(
        req.network_id, req.selected_types, req.save_to_region
    )
    return Success(data=data, msg="筛选完成")


class SegmentRequest(BaseModel):
    network_id: int = Field(..., description="路网文件ID")
    segment_length: float = Field(..., description="分段长度（米）")
    save_to_region: bool = Field(False, description="是否保存到区域下")


@router.post("/segment", summary="路网分段")
async def segment_network(req: SegmentRequest):
    data = await region_controller.segment_road_network(
        req.network_id, req.segment_length, req.save_to_region
    )
    return Success(data=data, msg="分段完成")


# ── 瓦片服务（独立 router，无需鉴权） ──
# Leaflet L.tileLayer 发起原生请求不带 JWT token，
# 因此瓦片端点注册为独立 router 绕过 DependPermission

tile_router = APIRouter()


@tile_router.delete("/tiles/cache", summary="清除路网瓦片缓存")
async def clear_tile_cache(network_id: int = Query(..., description="路网文件ID")):
    data = await region_controller.clear_tile_cache(network_id)
    return Success(data=data)


@tile_router.post("/warm-cache", summary="预热路网图缓存")
async def warm_tile_cache(network_id: int = Query(..., description="路网文件ID")):
    """后台预加载路网图到内存缓存，加速后续瓦片请求"""
    data = await region_controller.warm_tile_cache(network_id)
    return Success(data=data)


@tile_router.get("/tiles/{network_id}/{z}/{x}/{y}.png", summary="路网瓦片")
async def get_tile(
    network_id: int,
    z: int,
    x: int,
    y: int,
    types: str = Query("", description="筛选道路等级，逗号分隔，如 motorway,trunk"),
):
    """
    返回路网渲染的 256×256 PNG 瓦片。

    配合 Leaflet L.tileLayer 使用：
        L.tileLayer('/api/v1/region/road-network/tiles/{network_id}/{z}/{x}/{y}.png?types=motorway,trunk')

    缓存策略：
        - 磁盘缓存：uploads/tiles/{network_id}/{filter_key}/{z}/{x}/{y}.png
        - 内存图缓存：最近 5 个路网图对象（含空间索引）
    """
    # 防御：净化 types 参数，去除引号/括号等非字母字符
    raw_types = [t.strip() for t in types.split(",") if t.strip()] if types else []
    selected_types = []
    for t in raw_types:
        cleaned = "".join(c for c in t if c.isascii() and (c.isalnum() or c == "_"))
        if cleaned and len(cleaned) < 50:
            selected_types.append(cleaned)
    if not selected_types:
        selected_types = None

    png_bytes = await region_controller.get_tile(network_id, z, x, y, selected_types)
    return Response(
        content=png_bytes,
        media_type="image/png",
        headers={
            "Cache-Control": "public, max-age=3600",
            "Content-Length": str(len(png_bytes)),
        },
    )


@tile_router.get("/tile-proxy/{z}/{x}/{y}.png", summary="瓦片代理转发")
async def get_tile_proxy(
    z: int,
    x: int,
    y: int,
    url: str = Query(..., description="Base64 编码的目标瓦片 URL 模板（含 {z}/{x}/{y} 占位符）"),
):
    """
    通过后端代理转发瓦片请求到外部瓦片服务器。

    后端从系统配置读取 download_proxy，使用代理发起请求。
    适用于前端无法直接访问外部瓦片服务的网络环境。

    用法：
        L.tileLayer('/api/v1/region/road-network/tile-proxy/{z}/{x}/{y}.png?url={base64_template}')

    其中 base64_template 为目标 URL 模板的 Base64 编码，如：
        btoa('https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}')
    """
    # 1. 解码目标 URL 模板
    try:
        template = base64.b64decode(url).decode("utf-8")
    except Exception:
        return Response(
            content=b"",
            media_type="image/png",
            status_code=400,
        )

    # 2. 替换占位符
    target_url = template.replace("{x}", str(x)).replace("{y}", str(y)).replace("{z}", str(z))

    # 3. 从系统配置读取代理
    proxy_url = None
    ssl_verify = True
    try:
        proxy_val = await system_config_controller.get_value("download_proxy", "")
        if proxy_val:
            proxy_url = str(proxy_val).strip()
        ssl_val = await system_config_controller.get_value("download_ssl_verify", "true")
        ssl_verify = str(ssl_val).lower() != "false"
    except Exception:
        pass

    # 4. 通过代理请求目标瓦片
    client_kwargs = {
        "timeout": httpx.Timeout(15.0),
        "follow_redirects": True,
    }
    if proxy_url:
        client_kwargs["proxy"] = proxy_url
    if not ssl_verify:
        client_kwargs["verify"] = False

    try:
        async with httpx.AsyncClient(**client_kwargs) as client:
            resp = await client.get(target_url, headers={
                "User-Agent": "VansRSA-TileProxy/1.0",
                "Referer": "https://www.openstreetmap.org/",
            })
            if resp.status_code != 200:
                return Response(
                    content=b"",
                    media_type="image/png",
                    status_code=resp.status_code,
                )

            content_type = resp.headers.get("content-type", "image/png")
            return Response(
                content=resp.content,
                media_type=content_type,
                headers={
                    "Cache-Control": "public, max-age=3600",
                    "Content-Length": str(len(resp.content)),
                },
            )
    except httpx.ProxyError as e:
        logger.warning(f"瓦片代理连接失败 (proxy={proxy_url}): {e}")
        return Response(content=b"", media_type="image/png", status_code=502)
    except httpx.TimeoutException:
        logger.warning(f"瓦片代理超时: {target_url}")
        return Response(content=b"", media_type="image/png", status_code=504)
    except Exception as e:
        logger.warning(f"瓦片代理请求异常: {e}")
        return Response(content=b"", media_type="image/png", status_code=502)


# ── 筛选模板管理 ──

@router.get("/filter-templates", summary="获取筛选模板列表")
async def list_filter_templates():
    data = await region_controller.list_filter_templates()
    return Success(data=data)


@router.post("/filter-templates/create", summary="创建筛选模板")
async def create_filter_template(req: FilterTemplateCreate):
    data = await region_controller.create_filter_template(req.name, req.selected_types)
    return Success(data=data, msg="模板已创建")


@router.delete("/filter-templates/delete", summary="删除筛选模板")
async def delete_filter_template(template_id: int = Query(..., description="模板ID")):
    await region_controller.delete_filter_template(template_id)
    return Success(msg="模板已删除")


# ── 路网字段参数表 ──

@router.get("/fields", summary="获取路网字段参数（分页）")
async def get_fields(
    network_id: int = Query(..., description="路网文件ID"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(50, ge=1, le=500, description="每页数量"),
    search: str = Query("", description="搜索字段值"),
):
    data = await region_controller.get_road_fields(network_id, page, page_size, search)
    return SuccessExtra(data=data["rows"], total=data["total"], page=page, page_size=page_size)


@router.get("/fields/export", summary="导出路网字段全量 JSON")
async def export_fields(network_id: int = Query(..., description="路网文件ID")):
    data = await region_controller.export_road_fields_json(network_id)
    return Success(data=data)


class ImportFieldsRequest(BaseModel):
    network_id: int = Field(..., description="路网文件ID")
    edges: list = Field(..., description="边数据列表（完整字段）")


@router.post("/fields/import", summary="导入 JSON 重建路网字段")
async def import_fields(req: ImportFieldsRequest):
    data = await region_controller.import_road_fields_json(req.network_id, req.edges)
    return Success(data=data, msg="导入完成")


class BatchUpdateRequest(BaseModel):
    network_id: int = Field(..., description="路网文件ID")
    field: str = Field(..., description="目标字段名")
    mode: str = Field(..., description="操作模式: set(设统一值) | sanitize(数组取首值)")
    value: str = Field("", description="set 模式的新值")


@router.post("/fields/batch-update", summary="批量操作字段值")
async def batch_update_field(req: BatchUpdateRequest):
    data = await region_controller.batch_update_road_field(req.network_id, req.field, req.mode, req.value)
    return Success(data=data, msg=f"已处理 {data['affected']} 条边")


class AIProcessRequest(BaseModel):
    network_id: int = Field(..., description="路网文件ID")
    ai_proxy_id: int = Field(..., description="AI代理ID")
    prompt: str = Field(..., description="处理需求描述")
    sample: dict = Field(..., description="当前表格一条样本边数据（含所有字段）")
    fields_list: list = Field(..., description="字段名列表")
    skill_id: Optional[int] = Field(None, description="Skill ID（可选）")


@router.post("/fields/ai-process", summary="AI代理处理路网字段")
async def ai_process_fields(req: AIProcessRequest):
    data = await region_controller.process_fields_with_ai(
        network_id=req.network_id,
        ai_proxy_id=req.ai_proxy_id,
        prompt=req.prompt,
        sample=req.sample,
        fields_list=req.fields_list,
        skill_id=req.skill_id,
    )
    return Success(data=data)
