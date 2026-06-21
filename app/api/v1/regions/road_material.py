"""路网素材 API"""
import os
from typing import List

from fastapi import APIRouter, Body, Query, UploadFile, File, Form
from fastapi.responses import FileResponse, StreamingResponse
from tortoise.expressions import Q

from app.controllers.ai_proxy import ai_proxy_controller
from app.controllers.road_material import road_material_controller
from app.controllers.skill import skill_controller
from app.log import logger
from app.models.admin import RoadMaterial, Skill
from app.schemas.base import Fail, Success, SuccessExtra
from app.schemas.road_material import (
    AIMaterialProcessRequest,
    CVMaterialProcessRequest,
    RoadMaterialCreate,
    RoadMaterialUpdate,
)
from app.utils.image_processor import ImageProcessor
from app.utils.volcengine_visual import volcengine_visual

router = APIRouter()


# ── CRUD ──

@router.get("/list", summary="素材列表查询")
async def list_materials(
    page: int = Query(1, description="页码", ge=1),
    page_size: int = Query(20, description="每页数量", ge=1, le=500),
    region_id: int = Query(None, description="区域ID（可选）"),
    name: str = Query("", description="名称搜索"),
    source: str = Query("", description="来源筛选"),
):
    total, data = await road_material_controller.list_materials(
        page=page, page_size=page_size,
        region_id=region_id, name=name, source=source,
    )
    return SuccessExtra(data=data, total=total, page=page, page_size=page_size)


@router.get("/get", summary="查看素材详情")
async def get_material(material_id: int = Query(..., description="素材ID")):
    data = await road_material_controller.get_material(material_id)
    if not data:
        return Fail(code=404, msg="素材不存在")
    return Success(data=data)


@router.delete("/delete", summary="删除素材")
async def delete_material(material_id: int = Query(..., description="素材ID")):
    ok = await road_material_controller.delete_material(material_id)
    if not ok:
        return Fail(code=404, msg="素材不存在")
    return Success(msg="删除成功")


@router.put("/update", summary="更新素材元数据")
async def update_material(obj_in: RoadMaterialUpdate):
    await road_material_controller.update(id=obj_in.id, obj_in=obj_in.model_dump(exclude_unset=True, exclude={"id"}))
    return Success(msg="更新成功")


# ── 上传 ──

@router.post("/upload", summary="上传图片素材")
async def upload_material(
    region_id: int = Query(..., description="所属区域ID"),
    name: str = Form("", description="图片名称（可选，默认文件名）"),
    description: str = Form("", description="元数据（文本）"),
    source: str = Form("upload", description="图片来源"),
    file: UploadFile = File(..., description="图片文件"),
):
    if not file.filename:
        return Fail(code=400, msg="请选择文件")

    # 校验文件类型
    allowed_exts = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff", ".tif", ".webp", ".svg"}
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in allowed_exts:
        return Fail(code=400, msg=f"不支持的文件类型: {ext}，仅支持 {', '.join(sorted(allowed_exts))}")

    file_data = await file.read()
    if len(file_data) == 0:
        return Fail(code=400, msg="文件为空")

    obj = await road_material_controller.upload_material(
        region_id=region_id,
        file_data=file_data,
        original_filename=file.filename,
        name=name,
        description=description,
        source=source,
    )
    data = road_material_controller._to_output(obj)
    return Success(data=data, msg="上传成功")


# ── 下载/预览 ──

@router.get("/download-file", summary="下载原始图片文件")
async def download_file(material_id: int = Query(..., description="素材ID")):
    obj = await road_material_controller.get(id=material_id)
    if not obj or not os.path.exists(obj.file_path):
        return Fail(code=404, msg="文件不存在")
    ext = os.path.splitext(obj.file_name)[1] or ".png"
    base = obj.name or os.path.splitext(obj.file_name)[0]
    media_type_map = {
        ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
        ".gif": "image/gif", ".bmp": "image/bmp", ".tiff": "image/tiff",
        ".tif": "image/tiff", ".webp": "image/webp", ".svg": "image/svg+xml",
    }
    media_type = media_type_map.get(ext.lower(), "application/octet-stream")
    return FileResponse(
        obj.file_path,
        media_type=media_type,
        filename=base + ext,
    )


# ── AI 处理 ──

@router.post("/ai-process", summary="AI图片优化处理")
async def ai_process(req: AIMaterialProcessRequest):
    """使用 AI 代理对图片进行优化处理"""
    # 获取 AI 代理
    proxy = await ai_proxy_controller.get(id=req.ai_proxy_id)
    if not proxy:
        return Fail(code=404, msg="AI代理不存在")

    # 解析凭证
    try:
        ak, sk, req_key = volcengine_visual.parse_ai_proxy_credentials(
            proxy.token or "", proxy.model or ""
        )
    except ValueError as e:
        return Fail(code=400, msg=str(e))

    # 获取提示词
    prompt = req.prompt or ""
    if req.skill_id:
        skill = await skill_controller.get(id=req.skill_id)
        if skill:
            prompt = skill.content or prompt

    if not prompt:
        return Fail(code=400, msg="请提供处理提示词或选择 Skill")

    results = []
    errors = []

    for mid in req.material_ids:
        try:
            obj = await road_material_controller.get(id=mid)
            if not obj:
                errors.append({"material_id": mid, "error": "素材不存在"})
                continue

            # 读取原始图片
            with open(obj.file_path, "rb") as f:
                image_data = f.read()

            # 调用 AI
            processed_data = await volcengine_visual.process_image(
                image_data=image_data,
                access_key=ak,
                secret_key=sk,
                req_key=req_key,
                prompt=prompt,
            )

            # 保存为新素材
            new_obj = await road_material_controller.save_processed(
                original=obj,
                processed_data=processed_data,
                suffix="_ai",
                source="ai_generated",
                ext=".png",
            )
            results.append(road_material_controller._to_output(new_obj))

        except Exception as e:
            logger.exception(f"AI处理素材 {mid} 失败")
            errors.append({"material_id": mid, "error": str(e)})

    return Success(data={
        "results": results,
        "errors": errors,
        "total": len(req.material_ids),
        "success_count": len(results),
        "error_count": len(errors),
    })


# ── OpenCV 处理 ──

@router.post("/cv-process", summary="OpenCV图片处理")
async def cv_process(req: CVMaterialProcessRequest):
    """使用 OpenCV 对图片进行处理"""
    from app.schemas.road_material import CV_OPERATIONS

    if req.operation not in CV_OPERATIONS:
        return Fail(code=400, msg=f"不支持的操作: {req.operation}，可选: {list(CV_OPERATIONS.keys())}")

    results = []
    errors = []

    for mid in req.material_ids:
        try:
            obj = await road_material_controller.get(id=mid)
            if not obj:
                errors.append({"material_id": mid, "error": "素材不存在"})
                continue

            filepath = obj.file_path
            if not os.path.exists(filepath):
                errors.append({"material_id": mid, "error": "文件不存在"})
                continue

            params = req.params or {}
            proc = ImageProcessor()

            # 根据操作类型调用对应方法
            op = req.operation
            if op == "resize":
                processed = proc.resize(filepath, width=params.get("width", 800), height=params.get("height", 0))
            elif op == "rotate":
                processed = proc.rotate(filepath, angle=params.get("angle", 90), scale=params.get("scale", 1.0))
            elif op == "crop":
                processed = proc.crop(filepath,
                    x=params.get("x", 0), y=params.get("y", 0),
                    width=params.get("width", 200), height=params.get("height", 200))
            elif op == "flip":
                processed = proc.flip(filepath, direction=params.get("direction", 1))
            elif op == "border":
                processed = proc.add_border(filepath,
                    top=params.get("top", 10), bottom=params.get("bottom", 10),
                    left=params.get("left", 10), right=params.get("right", 10),
                    color=params.get("color", "#000000"))
            elif op == "brightness":
                processed = proc.brightness(filepath, value=params.get("value", 1.0))
            elif op == "contrast":
                processed = proc.contrast(filepath, value=params.get("value", 1.0))
            elif op == "color_space":
                processed = proc.color_space(filepath, target=params.get("target", "GRAY"))
            elif op == "blur":
                processed = proc.blur(filepath,
                    kernel_size=params.get("kernel_size", 5),
                    blur_type=params.get("type", "gaussian"))
            elif op == "morphology":
                processed = proc.morphology(filepath,
                    operation=params.get("operation", "erode"),
                    kernel_size=params.get("kernel_size", 3),
                    iterations=params.get("iterations", 1))
            elif op == "smooth":
                processed = proc.smooth(filepath,
                    method=params.get("method", "bilateral"),
                    h=params.get("h", 10),
                    template_window=params.get("template_window", 7),
                    search_window=params.get("search_window", 21))
            elif op == "histogram_eq":
                processed = proc.histogram_eq(filepath,
                    method=params.get("method", "global"),
                    clip_limit=params.get("clip_limit", 2.0),
                    tile_size=params.get("tile_size", 8))
            elif op == "remove_bg":
                processed = proc.remove_bg(filepath,
                    method=params.get("method", "grabcut"),
                    margin=params.get("margin", 10))
            else:
                errors.append({"material_id": mid, "error": f"未实现的操作: {op}"})
                continue

            # 生成后缀
            suffix = f"_{op}"
            new_obj = await road_material_controller.save_processed(
                original=obj,
                processed_data=processed,
                suffix=suffix,
                source="cv_processed",
                ext=".png",
            )
            results.append(road_material_controller._to_output(new_obj))

        except Exception as e:
            logger.exception(f"OpenCV处理素材 {mid} 失败")
            errors.append({"material_id": mid, "error": str(e)})

    return Success(data={
        "results": results,
        "errors": errors,
        "total": len(req.material_ids),
        "success_count": len(results),
        "error_count": len(errors),
    })


# ── 获取操作列表 ──

@router.get("/cv-operations", summary="获取支持的OpenCV操作列表")
async def get_cv_operations():
    from app.schemas.road_material import CV_OPERATIONS
    return Success(data=CV_OPERATIONS)


# ── 短链接公开访问（无需鉴权） ──
# 此路由单独注册，不加 DependPermission

short_router = APIRouter()


@short_router.get("/{token}", summary="短链接访问图片（无需鉴权）")
async def short_url_access(token: str):
    """通过短链接令牌访问图片，无需登录，永久有效"""
    obj = await road_material_controller.get_by_short_token(token)
    if not obj or not os.path.exists(obj.file_path):
        return Fail(code=404, msg="文件不存在或链接已失效")

    ext = os.path.splitext(obj.file_name)[1] or ".png"
    base = obj.name or os.path.splitext(obj.file_name)[0]
    media_type_map = {
        ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
        ".gif": "image/gif", ".bmp": "image/bmp", ".tiff": "image/tiff",
        ".tif": "image/tiff", ".webp": "image/webp", ".svg": "image/svg+xml",
    }
    media_type = media_type_map.get(ext.lower(), "application/octet-stream")
    return FileResponse(
        obj.file_path,
        media_type=media_type,
        filename=base + ext,
    )