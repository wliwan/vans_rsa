"""静态文件数据 API"""
import os
from typing import List

from fastapi import APIRouter, File, Form, Query, UploadFile
from fastapi.responses import FileResponse

from app.controllers.ai_proxy import ai_proxy_controller
from app.controllers.skill import skill_controller
from app.controllers.static_file import static_file_controller
from app.controllers.workspace import workspace_controller
from app.core.ctx import CTX_USER_ID
from app.log import logger
from app.schemas.base import Fail, Success, SuccessExtra
from app.schemas.static_file import (
    AIProcessRequest, BatchDeleteRequest, CVProcessRequest,
    CV_OPERATIONS, ImportRoadMaterialRequest, OCRRequest,
    StaticFileUpdate,
)

router = APIRouter()


# ── 列表 ──

@router.get("/list", summary="查看静态文件列表（按层级）")
async def list_files(
    workspace_id: int = Query(..., description="工作区ID"),
    source_type: str = Query("original", description="目录层级: original / ai_analysis"),
    page: int = Query(1, description="页码", ge=1),
    page_size: int = Query(50, description="每页数量", ge=1, le=500),
):
    user_id = CTX_USER_ID.get()
    ws = await workspace_controller.check_permission(workspace_id, user_id)
    if not ws:
        return Fail(code=403, msg="无权访问该工作区")
    total, data = await static_file_controller.list_files(
        workspace_id=workspace_id, source_type=source_type,
        page=page, page_size=page_size,
    )
    return SuccessExtra(data=data, total=total, page=page, page_size=page_size)


# ── 上传 ──

@router.post("/upload", summary="上传文件到静态文件区")
async def upload_file(
    workspace_id: int = Query(..., description="工作区ID"),
    source_type: str = Query("original", description="目标层级: original / ai_analysis"),
    name: str = Form("", description="文件名称（可选）"),
    description: str = Form("", description="元数据（文本）"),
    file: UploadFile = File(..., description="文件"),
):
    user_id = CTX_USER_ID.get()
    ws = await workspace_controller.check_permission(workspace_id, user_id)
    if not ws:
        return Fail(code=403, msg="无权操作该工作区")
    if not file.filename:
        return Fail(code=400, msg="请选择文件")

    file_data = await file.read()
    if len(file_data) == 0:
        return Fail(code=400, msg="文件为空")

    obj = await static_file_controller.upload(
        workspace_id=workspace_id,
        file_data=file_data,
        original_filename=file.filename,
        name=name,
        description=description,
        source_type=source_type,
    )
    data = static_file_controller._to_output(obj)
    return Success(data=data, msg="上传成功")


@router.post("/batch-upload", summary="批量上传文件到静态文件区")
async def batch_upload_files(
    workspace_id: int = Query(..., description="工作区ID"),
    source_type: str = Query("original", description="目标层级: original / ai_analysis"),
    name_prefix: str = Form("", description="批量文件名称前缀（可选）"),
    description: str = Form("", description="批量文件描述（可选）"),
    files: List[UploadFile] = File(..., description="文件列表"),
):
    user_id = CTX_USER_ID.get()
    ws = await workspace_controller.check_permission(workspace_id, user_id)
    if not ws:
        return Fail(code=403, msg="无权操作该工作区")
    success_list, error_list = [], []
    for idx, file in enumerate(files):
        if not file.filename:
            error_list.append({"filename": "未知", "reason": "文件名为空"})
            continue
        file_data = await file.read()
        if len(file_data) == 0:
            error_list.append({"filename": file.filename, "reason": "文件为空"})
            continue
        display_name = name_prefix or ""
        if name_prefix and len(files) > 1:
            display_name = f"{name_prefix}_{idx + 1}"
        try:
            obj = await static_file_controller.upload(
                workspace_id=workspace_id,
                file_data=file_data,
                original_filename=file.filename,
                name=display_name,
                description=description,
                source_type=source_type,
            )
            success_list.append(static_file_controller._to_output(obj))
        except Exception as e:
            logger.warning(f"批量上传静态文件失败 [{file.filename}]: {e}")
            error_list.append({"filename": file.filename, "reason": str(e)})
    return Success(
        data={
            "success": success_list,
            "errors": error_list,
            "total": len(files),
            "success_count": len(success_list),
            "error_count": len(error_list),
        },
        msg=f"上传完成：成功 {len(success_list)} 个，失败 {len(error_list)} 个",
    )


# ── 详情 ──

@router.get("/get", summary="获取静态文件详情")
async def get_file(file_id: int = Query(..., description="文件ID")):
    data = await static_file_controller.get_file(file_id)
    if not data:
        return Fail(code=404, msg="文件不存在")
    return Success(data=data)


# ── 更新元数据 ──

@router.put("/update", summary="更新文件元数据")
async def update_file(obj_in: StaticFileUpdate):
    ok = await static_file_controller.update_file(
        file_id=obj_in.id, name=obj_in.name, description=obj_in.description,
    )
    if not ok:
        return Fail(code=404, msg="文件不存在")
    return Success(msg="更新成功")


# ── 删除 ──

@router.delete("/delete", summary="删除静态文件")
async def delete_file(file_id: int = Query(..., description="文件ID")):
    ok = await static_file_controller.delete_file(file_id)
    if not ok:
        return Fail(code=404, msg="文件不存在")
    return Success(msg="删除成功")


@router.post("/batch-delete", summary="批量删除静态文件")
async def batch_delete_files(req: BatchDeleteRequest):
    deleted = await static_file_controller.batch_delete(req.file_ids)
    return Success(data={"deleted": deleted}, msg=f"已删除 {deleted} 个文件")


# ── 下载 ──

@router.get("/download-file", summary="下载静态文件（不鉴权短链接也走这里？用有权限的下载）")
async def download_file(file_id: int = Query(..., description="文件ID")):
    obj = await static_file_controller.get(id=file_id)
    if not obj or not os.path.exists(obj.file_path):
        return Fail(code=404, msg="文件不存在")
    return FileResponse(
        obj.file_path,
        filename=obj.file_name,
        media_type="application/octet-stream",
    )


# ── 获取 OpenCV 操作列表 ──

@router.get("/cv-operations", summary="获取支持的 OpenCV 操作列表")
async def get_cv_operations():
    return Success(data=CV_OPERATIONS)


# ── OpenCV 处理 ──

@router.post("/cv-process", summary="OpenCV 图片处理")
async def cv_process_files(req: CVProcessRequest):
    # 取第一张图的工作区ID
    first = await static_file_controller.get(id=req.file_ids[0]) if req.file_ids else None
    if not first:
        return Fail(code=404, msg="文件不存在")
    workspace_id = first["workspace_id"]
    user_id = CTX_USER_ID.get()
    ws = await workspace_controller.check_permission(workspace_id, user_id)
    if not ws:
        return Fail(code=403, msg="无权操作该工作区")
    results, errors = await static_file_controller.cv_process(
        file_ids=req.file_ids, operation=req.operation,
        params=req.params, workspace_id=workspace_id,
    )
    return Success(data={
        "results": results, "errors": errors,
        "total": len(req.file_ids), "success_count": len(results), "error_count": len(errors),
    }, msg=f"OpenCV 处理完成：成功 {len(results)} 个，失败 {len(errors)} 个")


# ── AI 处理 ──

@router.post("/ai-process", summary="AI 图片处理")
async def ai_process_files(req: AIProcessRequest):
    # 取第一张图的工作区ID
    first = await static_file_controller.get(id=req.file_ids[0]) if req.file_ids else None
    if not first:
        return Fail(code=404, msg="文件不存在")
    workspace_id = first["workspace_id"]
    user_id = CTX_USER_ID.get()
    ws = await workspace_controller.check_permission(workspace_id, user_id)
    if not ws:
        return Fail(code=403, msg="无权操作该工作区")

    # 从 Skill 填充 prompt
    final_prompt = req.prompt or ""
    if req.skill_id and not final_prompt:
        skill = await skill_controller.get(id=req.skill_id)
        if skill:
            final_prompt = skill.content

    try:
        results, errors = await static_file_controller.ai_process(
            file_ids=req.file_ids, ai_proxy_id=req.ai_proxy_id,
            prompt=final_prompt, workspace_id=workspace_id,
        )
        return Success(data={
            "results": results, "errors": errors,
            "total": len(req.file_ids), "success_count": len(results), "error_count": len(errors),
        }, msg=f"AI 处理完成：成功 {len(results)} 个，失败 {len(errors)} 个")
    except ValueError as e:
        return Fail(code=400, msg=str(e))


# ── OCR 提取 ──

@router.post("/ocr", summary="OCR 文本提取")
async def ocr_extract_files(req: OCRRequest):
    user_id = CTX_USER_ID.get()
    ws = await workspace_controller.check_permission(req.workspace_id, user_id)
    if not ws:
        return Fail(code=403, msg="无权操作该工作区")
    docs, errors = await static_file_controller.ocr_extract(
        file_ids=req.file_ids, workspace_id=req.workspace_id,
    )
    return Success(data={
        "documents": docs, "errors": errors,
        "total": len(req.file_ids), "success_count": len(docs), "error_count": len(errors),
    }, msg=f"OCR 提取完成：成功 {len(docs)} 个，失败 {len(errors)} 个")


# ── 从路网素材导入 ──

@router.post("/import-from-material", summary="从路网素材导入")
async def import_from_road_material(req: ImportRoadMaterialRequest):
    user_id = CTX_USER_ID.get()
    ws = await workspace_controller.check_permission(req.workspace_id, user_id)
    if not ws:
        return Fail(code=403, msg="无权操作该工作区")
    results, errors = await static_file_controller.import_from_road_material(
        workspace_id=req.workspace_id, material_ids=req.material_ids,
    )
    return Success(data={
        "results": results, "errors": errors,
        "total": len(req.material_ids), "success_count": len(results), "error_count": len(errors),
    }, msg=f"导入完成：成功 {len(results)} 个，失败 {len(errors)} 个")


# ── 路网素材浏览 ──

@router.get("/material/regions", summary="获取有路网素材的区域列表")
async def get_material_regions():
    """返回所有有路网素材的区域，含完整层级路径，用于级联导航"""
    regions = await static_file_controller.list_material_regions()
    return Success(data=regions)


@router.get("/material/list-by-region", summary="获取某区域的路网素材列表")
async def list_materials_by_region(
    region_id: int = Query(..., description="区域ID"),
    page: int = Query(1, description="页码", ge=1),
    page_size: int = Query(500, description="每页数量", ge=1, le=500),
):
    total, data = await static_file_controller.list_materials_by_region(
        region_id=region_id, page=page, page_size=page_size,
    )
    return SuccessExtra(data=data, total=total, page=page, page_size=page_size)


# ── 图片文件列表 ──

@router.get("/images", summary="获取所有图片文件")
async def list_image_files(
    workspace_id: int = Query(..., description="工作区ID"),
    source_type: str = Query("original", description="目录层级: original / ai_analysis"),
):
    user_id = CTX_USER_ID.get()
    ws = await workspace_controller.check_permission(workspace_id, user_id)
    if not ws:
        return Fail(code=403, msg="无权访问该工作区")
    data = await static_file_controller.list_image_files(
        workspace_id=workspace_id, source_type=source_type,
    )
    return Success(data=data)


# ── 短链接访问（独立 router，无鉴权）──
short_router = APIRouter()

@short_router.get("/{token}", summary="通过短链接访问静态文件")
async def get_static_file_by_short_token(token: str):
    """通过短链接令牌访问文件，无需登录，永久有效"""
    obj = await static_file_controller.get_by_short_token(token)
    if not obj or not os.path.exists(obj.file_path):
        return Fail(code=404, msg="文件不存在或链接已失效")
    return FileResponse(
        obj.file_path,
        filename=obj.file_name,
        media_type="application/octet-stream",
    )

