"""行政区边界文件 API"""
from fastapi import APIRouter, Query, UploadFile, File

from app.controllers.region import region_controller
from app.utils.http_utils import make_download_response
from app.schemas.base import Success
from app.schemas.regions import BoundaryDownloadRequest

router = APIRouter()


@router.get("/status", summary="检查边界文件状态")
async def check_boundary_status(region_id: int = Query(..., description="区域ID")):
    data = await region_controller.get_boundary_status(region_id)
    return Success(data=data)


@router.post("/download", summary="从在线服务下载边界文件")
async def download_boundary(req: BoundaryDownloadRequest):
    data = await region_controller.download_boundary(req.region_id, req.file_type.value)
    return Success(data=data, msg="下载成功")


@router.post("/upload", summary="上传边界文件")
async def upload_boundary(
    region_id: int = Query(..., description="区域ID"),
    file: UploadFile = File(...),
):
    content = await file.read()
    data = await region_controller.upload_boundary(region_id, content, file.filename or "boundary.geojson")
    return Success(data=data, msg="上传成功")


@router.delete("/delete", summary="删除单个边界文件")
async def delete_boundary(boundary_id: int = Query(..., description="边界文件ID")):
    await region_controller.delete_boundary(boundary_id)
    return Success(msg="Deleted Successfully")


@router.delete("/clear", summary="清除区域所有边界文件")
async def clear_boundaries(region_id: int = Query(..., description="区域ID")):
    count = await region_controller.clear_boundaries(region_id)
    return Success(data={"deleted": count}, msg=f"已清除 {count} 个文件")


@router.get("/download-file", summary="下载/导出边界文件")
async def download_boundary_file(boundary_id: int = Query(..., description="边界文件ID")):
    file_path, file_name, media_type = await region_controller.export_boundary(boundary_id)
    return make_download_response(
        path=file_path, filename=file_name, media_type=media_type)
