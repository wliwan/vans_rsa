"""静态文件数据 API"""
import io
import os
import zipfile
from typing import List

from fastapi import APIRouter, File, Form, Query, UploadFile
from fastapi.responses import FileResponse, StreamingResponse

from app.controllers.ai_proxy import ai_proxy_controller
from app.controllers.skill import skill_controller
from app.controllers.static_file import static_file_controller
from app.controllers.system_config import system_config_controller
from app.controllers.workspace import workspace_controller
from app.core.ctx import CTX_USER_ID
from app.log import logger
from app.schemas.base import Fail, Success, SuccessExtra
from app.schemas.static_file import (
    AIProcessRequest, BatchDeleteRequest, CopyRecordsRequest, CVProcessRequest,
    CV_OPERATIONS, ImportExtractedImagesRequest, ImportRoadMaterialRequest, OCRRequest,
    SetBaseUrlRequest, StaticFileUpdate,
)

router = APIRouter()


# ── 列表 ──

@router.get("/list", summary="查看静态文件列表（按层级）")
async def list_files(
    workspace_id: int = Query(..., description="工作区ID"),
    source_type: str = Query("original", description="目录层级: original / ai_analysis"),
    page: int = Query(1, description="页码", ge=1),
    page_size: int = Query(50, description="每页数量", ge=1, le=99999),
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


# ── 复制到工作区 ──

@router.post("/copy-records", summary="复制文件记录到另一工作区（不拷贝物理文件）")
async def copy_records(req: CopyRecordsRequest):
    """只创建数据库记录指向同一物理文件，生成新短链接令牌"""
    user_id = CTX_USER_ID.get()
    ws = await workspace_controller.check_permission(req.target_workspace_id, user_id)
    if not ws:
        return Fail(code=403, msg="无权操作目标工作区")
    results, errors = await static_file_controller.copy_records(
        file_ids=req.file_ids, target_workspace_id=req.target_workspace_id,
    )
    return Success(data={
        "results": results, "errors": errors,
        "total": len(req.file_ids), "success_count": len(results), "error_count": len(errors),
    }, msg=f"复制完成：成功 {len(results)} 个，失败 {len(errors)} 个")


# ── 批量导出 ──

@router.post("/batch-export", summary="批量导出静态文件（ZIP压缩包）")
async def batch_export_files(req: BatchDeleteRequest):
    """批量导出选中的静态文件为 ZIP 压缩包，返回下载"""
    user_id = CTX_USER_ID.get()
    buf = io.BytesIO()
    exported = 0
    skipped = []
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for fid in req.file_ids:
            obj = await static_file_controller.get(id=fid)
            if not obj:
                skipped.append({"file_id": fid, "reason": "文件不存在"})
                continue
            ws = await workspace_controller.check_permission(obj["workspace_id"], user_id)
            if not ws:
                skipped.append({"file_id": fid, "reason": "无权访问该工作区"})
                continue
            filepath = obj["file_path"]
            if not os.path.exists(filepath):
                skipped.append({"file_id": fid, "reason": "文件已丢失"})
                continue
            arcname = obj["file_name"]
            # 处理重名
            counter = 1
            name_part, ext_part = os.path.splitext(arcname)
            existing_names = {n for n in zf.namelist()}
            while arcname in existing_names:
                arcname = f"{name_part}_{counter}{ext_part}"
                counter += 1
            zf.write(filepath, arcname=arcname)
            exported += 1
    if exported == 0:
        return Fail(code=404, msg="没有可导出的文件", data={"skipped": skipped})
    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="static_files_{exported}.zip"'},
    )


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


# ── BaseUrl 配置 ──

_BASE_URL_KEY = "static_file_base_url"

@router.get("/base-url", summary="获取静态文件 BaseUrl")
async def get_base_url():
    url = await system_config_controller.get_value(_BASE_URL_KEY, "")
    return Success(data={"base_url": url})


@router.put("/base-url", summary="设置静态文件 BaseUrl")
async def set_base_url(req: SetBaseUrlRequest):
    await system_config_controller.set_value(_BASE_URL_KEY, req.base_url.strip())
    return Success(msg="BaseUrl 已更新", data={"base_url": req.base_url.strip()})


# ── 文档图片提取 ──

@router.post("/extract-images", summary="从文档中提取图片（PPT/Word/Excel/PDF）")
async def extract_images_from_document(
    file: UploadFile = File(..., description="文档文件(.ppt/.pptx/.doc/.docx/.xls/.xlsx/.pdf)"),
):
    if not file.filename:
        return Fail(code=400, msg="请选择文件")
    file_data = await file.read()
    if len(file_data) == 0:
        return Fail(code=400, msg="文件为空")
    try:
        images = await static_file_controller.extract_images_from_document(
            file_data=file_data, original_filename=file.filename,
        )
        # 返回时移除 temp_path（前端不需要知道服务器路径），保留 index 用于导入选择
        safe_images = []
        for img in images:
            safe_images.append({
                k: v for k, v in img.items() if not k.startswith("temp_")
            })
        return Success(data={
            "images": safe_images,
            "count": len(safe_images),
            "temp_paths": [img["temp_path"] for img in images],  # 前端后续导入需要回传
            "source_name": file.filename,
        }, msg=f"提取完成：共 {len(safe_images)} 张图片")
    except ValueError as e:
        return Fail(code=400, msg=str(e))
    except Exception as e:
        logger.exception("文档图片提取失败")
        return Fail(code=500, msg=f"提取失败: {str(e)}")


@router.post("/import-extracted", summary="导入从文档提取的图片到静态文件区")
async def import_extracted_images(req: ImportExtractedImagesRequest):
    user_id = CTX_USER_ID.get()
    ws = await workspace_controller.check_permission(req.workspace_id, user_id)
    if not ws:
        return Fail(code=403, msg="无权操作该工作区")
    results, errors = await static_file_controller.import_extracted_images(
        workspace_id=req.workspace_id,
        temp_paths=req.temp_paths,
        file_names=req.file_names,
        source_type=req.source_type,
        source_doc_name=req.source_doc_name,
    )
    return Success(data={
        "results": results, "errors": errors,
        "total": len(req.temp_paths),
        "success_count": len(results),
        "error_count": len(errors),
    }, msg=f"导入完成：成功 {len(results)} 个，失败 {len(errors)} 个")


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

