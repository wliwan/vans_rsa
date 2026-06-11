"""路网文件管理 API"""
from fastapi import APIRouter, File, Query, UploadFile

from pydantic import BaseModel, Field

from app.controllers.region import region_controller
from app.utils.http_utils import make_download_response
from app.schemas.base import Success
from app.schemas.regions import RoadNetworkDownloadRequest

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
