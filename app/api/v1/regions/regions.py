"""全球国家及行政区 API"""
from fastapi import APIRouter, Body, Query

from app.controllers.region import region_controller
from app.schemas.base import Success, SuccessExtra
from app.schemas.regions import (
    RegionBatchUpdate,
    RegionCreate,
    RegionExportRequest,
    RegionImportRequest,
    RegionUpdate,
)

router = APIRouter()


@router.get("/list", summary="列表查询")
async def list_regions(
    page: int = Query(1, description="页码"),
    page_size: int = Query(20, description="每页数量"),
    name: str = Query("", description="名称搜索"),
    code: str = Query("", description="代码搜索"),
    region_type: str = Query("", description="类型"),
    parent_id: int = Query(None, description="父级ID"),
    is_active: bool = Query(None, description="是否启用"),
):
    total, data = await region_controller.list_regions(
        page=page, page_size=page_size, name=name, code=code,
        region_type=region_type or None, parent_id=parent_id, is_active=is_active,
    )
    return SuccessExtra(data=data, total=total, page=page, page_size=page_size)


@router.get("/tree", summary="获取树结构")
async def get_tree():
    return Success(data=await region_controller.get_tree())


@router.get("/children", summary="获取子节点")
async def get_children(parent_id: int = Query(..., description="父级ID")):
    return Success(data=await region_controller.get_children(parent_id))


@router.get("/get", summary="查看详情")
async def get_region(region_id: int = Query(..., description="区域ID")):
    obj = await region_controller.get(id=region_id)
    data = await obj.to_dict()
    return Success(data=data)


@router.post("/create", summary="新增")
async def create_region(obj_in: RegionCreate):
    await region_controller.create_region(obj_in=obj_in)
    return Success(msg="Created Successfully")


@router.post("/update", summary="更新")
async def update_region(obj_in: RegionUpdate):
    await region_controller.update_region(obj_in=obj_in)
    return Success(msg="Updated Successfully")


@router.delete("/delete", summary="删除")
async def delete_region(region_id: int = Query(..., description="区域ID")):
    await region_controller.remove(id=region_id)
    return Success(msg="Deleted Successfully")


@router.post("/import", summary="批量导入ISO 3166国家")
async def import_countries(_: RegionImportRequest = None):
    return Success(data=await region_controller.import_countries())


@router.post("/clear", summary="全部清空")
async def clear_all():
    count = await region_controller.clear_all()
    return Success(data={"deleted": count})


@router.post("/export", summary="导出数据")
async def export_data(req: RegionExportRequest):
    data = await region_controller.export_data(req.country_id, req.level.value)
    return Success(data=data)


@router.post("/batch-update", summary="批量更新")
async def batch_update(req: RegionBatchUpdate):
    result = await region_controller.batch_update([u.model_dump(exclude_unset=True) for u in req.updates])
    return Success(data=result)


@router.post("/fill-geonames", summary="填充行政区中文名")
async def fill_geonames(
    force_download: bool = Body(False, embed=True),
    proxy: str | None = Body(None, embed=True),
):
    """从 GeoNames 下载中文名并填充 STATE/CITY 的 local_name

    body: {force_download: bool, proxy: "http://127.0.0.1:7890"}
    首次下载约 700MB（3-10 分钟），后续使用离线缓存秒级完成。
    """
    result = await region_controller.fill_geonames(
        force_download=force_download, proxy=proxy
    )
    return Success(data=result)


@router.get("/fill-geonames/progress", summary="下载进度查询")
async def geonames_progress():
    """查询 GeoNames 下载/填充进度"""
    return Success(data=region_controller.get_geonames_progress())
