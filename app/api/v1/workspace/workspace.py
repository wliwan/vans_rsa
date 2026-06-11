import io
import logging
import os
import zipfile

from fastapi import APIRouter, File, Query, UploadFile
from app.controllers.workspace import (
    AIAnalysisService,
    SheetService,
    workspace_controller,
)
from app.core.ctx import CTX_USER_ID
from app.models.admin import AnalysisSheet, OriginalSheet, Workspace
from app.schemas.base import Fail, Success, SuccessExtra
from app.schemas.workspace import *
from app.utils.http_utils import make_download_response

logger = logging.getLogger(__name__)

router = APIRouter()


# ==================== 工作区 CRUD ====================

@router.get("/list", summary="查看工作区列表")
async def list_workspaces(
    page: int = Query(1, description="页码"),
    page_size: int = Query(10, description="每页数量"),
):
    user_id = CTX_USER_ID.get()
    total, objs = await workspace_controller.get_accessible(user_id=user_id, page=page, page_size=page_size)
    data = [await obj.to_dict(m2m=True) for obj in objs]
    return SuccessExtra(data=data, total=total, page=page, page_size=page_size)


@router.post("/create", summary="创建工作区")
async def create_workspace(ws_in: WorkspaceCreate):
    user_id = CTX_USER_ID.get()
    obj_dict = ws_in.create_dict()
    ws = await Workspace.create(**obj_dict)
    all_ids = set(ws_in.user_ids)
    all_ids.add(user_id)
    await workspace_controller.update_users(ws, list(all_ids))
    return Success(msg="创建成功")


@router.post("/update", summary="更新工作区")
async def update_workspace(ws_in: WorkspaceUpdate):
    user_id = CTX_USER_ID.get()
    ws = await workspace_controller.check_permission(ws_in.id, user_id)
    if not ws:
        return Fail(code=403, msg="无权修改该工作区")
    await ws.update_from_dict(ws_in.model_dump(exclude_unset=True, exclude={"id", "user_ids"})).save()
    await workspace_controller.update_users(ws, ws_in.user_ids)
    return Success(msg="更新成功")


@router.delete("/delete", summary="删除工作区")
async def delete_workspace(workspace_id: int = Query(..., description="工作区ID")):
    user_id = CTX_USER_ID.get()
    ws = await workspace_controller.check_permission(workspace_id, user_id)
    if not ws:
        return Fail(code=403, msg="无权删除该工作区")
    # 删除关联的表格文件
    sheets = await OriginalSheet.filter(workspace_id=workspace_id).all()
    for s in sheets:
        if os.path.exists(s.file_path):
            os.remove(s.file_path)
    analyses = await AnalysisSheet.filter(workspace_id=workspace_id).all()
    for a in analyses:
        if os.path.exists(a.file_path):
            os.remove(a.file_path)
    await ws.delete()
    return Success(msg="删除成功")


@router.get("/users", summary="获取用户列表（权限选择）")
async def get_users():
    from app.models.admin import User
    users = await User.filter(is_active=True).all()
    data = [{"id": u.id, "username": u.username, "alias": u.alias} for u in users]
    return Success(data=data)


# ==================== 原始表格 ====================

@router.post("/sheet/upload", summary="上传表格")
async def upload_sheet(
    workspace_id: int = Query(..., description="工作区ID"),
    file: UploadFile = File(..., description="Excel文件"),
):
    user_id = CTX_USER_ID.get()
    ws = await workspace_controller.check_permission(workspace_id, user_id)
    if not ws:
        return Fail(code=403, msg="无权操作该工作区")
    if not file.filename or not file.filename.endswith((".xlsx", ".xls", ".csv")):
        return Fail(code=400, msg="仅支持 .xlsx / .xls / .csv 格式")
    sheet = await SheetService.upload_sheet(workspace_id, file)
    return Success(data=await sheet.to_dict(), msg="上传成功")


@router.get("/sheet/list", summary="原始表格列表")
async def list_sheets(workspace_id: int = Query(..., description="工作区ID")):
    user_id = CTX_USER_ID.get()
    ws = await workspace_controller.check_permission(workspace_id, user_id)
    if not ws:
        return Fail(code=403, msg="无权访问该工作区")
    sheets = await OriginalSheet.filter(workspace_id=workspace_id).order_by("-created_at").all()
    data = [await s.to_dict() for s in sheets]
    return Success(data=data)


@router.delete("/sheet/delete", summary="删除原始表格")
async def delete_sheet(sheet_id: int = Query(..., description="表格ID")):
    user_id = CTX_USER_ID.get()
    sheet = await OriginalSheet.get_or_none(id=sheet_id)
    if not sheet:
        return Fail(code=404, msg="表格不存在")
    ws = await workspace_controller.check_permission(sheet.workspace_id, user_id)
    if not ws:
        return Fail(code=403, msg="无权操作")
    if os.path.exists(sheet.file_path):
        os.remove(sheet.file_path)
    await sheet.delete()
    return Success(msg="删除成功")


@router.get("/sheet/export", summary="导出原始表格")
async def export_sheet(sheet_id: int = Query(..., description="表格ID")):
    user_id = CTX_USER_ID.get()
    sheet = await OriginalSheet.get_or_none(id=sheet_id)
    if not sheet:
        return Fail(code=404, msg="表格不存在")
    ws = await workspace_controller.check_permission(sheet.workspace_id, user_id)
    if not ws:
        return Fail(code=403, msg="无权导出")
    return make_download_response(
        path=sheet.file_path, filename=sheet.name,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


# ==================== AI 分析 ====================

@router.post("/analysis/analyze", summary="AI分析原始表格")
async def analyze_sheet(req: AnalysisRequest):
    user_id = CTX_USER_ID.get()
    ws = await workspace_controller.check_permission(req.workspace_id, user_id)
    if not ws:
        return Fail(code=403, msg="无权操作该工作区")
    try:
        analyses = await AIAnalysisService.analyze_sheet(
            workspace_id=req.workspace_id,
            sheet_id=req.sheet_id,
            ai_proxy_id=req.ai_proxy_id,
            name=req.name,
            skill_id=req.skill_id,
            extra_prompt=req.prompt or "",
        )
        return Success(data=[await a.to_dict() for a in analyses], msg=f"分析完成，生成{len(analyses)}个表格")
    except Exception as e:
        logger.exception("AI分析失败")
        return Fail(code=500, msg=f"分析失败: {str(e)}")


@router.post("/analysis/correlate", summary="AI关联分析")
async def correlate_sheets(req: CorrelationRequest):
    user_id = CTX_USER_ID.get()
    ws = await workspace_controller.check_permission(req.workspace_id, user_id)
    if not ws:
        return Fail(code=403, msg="无权操作该工作区")
    try:
        analyses = await AIAnalysisService.correlate_sheets(
            workspace_id=req.workspace_id,
            sheet_a_id=req.sheet_a_id,
            sheet_b_id=req.sheet_b_id,
            ai_proxy_id=req.ai_proxy_id,
            name=req.name,
            skill_id=req.skill_id,
            extra_prompt=req.prompt or "",
        )
        return Success(data=[await a.to_dict() for a in analyses], msg=f"关联分析完成，生成{len(analyses)}个表格")
    except Exception as e:
        logger.exception("关联分析失败")
        return Fail(code=500, msg=f"分析失败: {str(e)}")


@router.get("/analysis/list", summary="分析表格列表")
async def list_analyses(workspace_id: int = Query(..., description="工作区ID")):
    user_id = CTX_USER_ID.get()
    ws = await workspace_controller.check_permission(workspace_id, user_id)
    if not ws:
        return Fail(code=403, msg="无权访问该工作区")
    analyses = await AnalysisSheet.filter(workspace_id=workspace_id).order_by("-created_at").all()
    data = [await a.to_dict() for a in analyses]
    return Success(data=data)


@router.delete("/analysis/delete", summary="删除分析表格")
async def delete_analysis(analysis_id: int = Query(..., description="分析ID")):
    user_id = CTX_USER_ID.get()
    analysis = await AnalysisSheet.get_or_none(id=analysis_id)
    if not analysis:
        return Fail(code=404, msg="分析不存在")
    ws = await workspace_controller.check_permission(analysis.workspace_id, user_id)
    if not ws:
        return Fail(code=403, msg="无权操作")
    if os.path.exists(analysis.file_path):
        os.remove(analysis.file_path)
    await analysis.delete()
    return Success(msg="删除成功")


@router.post("/analysis/batch-delete", summary="批量删除分析表格")
async def batch_delete_analyses(req: BatchDeleteRequest):
    user_id = CTX_USER_ID.get()
    deleted = 0
    for aid in req.analysis_ids:
        analysis = await AnalysisSheet.get_or_none(id=aid)
        if not analysis:
            continue
        ws = await workspace_controller.check_permission(analysis.workspace_id, user_id)
        if not ws:
            continue
        if os.path.exists(analysis.file_path):
            os.remove(analysis.file_path)
        await analysis.delete()
        deleted += 1
    return Success(msg=f"已删除 {deleted} 个分析表格")


@router.delete("/analysis/clear", summary="清空全部分析表格")
async def clear_analyses(workspace_id: int = Query(..., description="工作区ID")):
    user_id = CTX_USER_ID.get()
    ws = await workspace_controller.check_permission(workspace_id, user_id)
    if not ws:
        return Fail(code=403, msg="无权操作")
    analyses = await AnalysisSheet.filter(workspace_id=workspace_id).all()
    for a in analyses:
        if os.path.exists(a.file_path):
            os.remove(a.file_path)
        await a.delete()
    return Success(msg=f"已清空 {len(analyses)} 个分析表格")


@router.get("/analysis/export", summary="导出分析表格")
async def export_analysis(analysis_id: int = Query(..., description="分析ID")):
    user_id = CTX_USER_ID.get()
    analysis = await AnalysisSheet.get_or_none(id=analysis_id)
    if not analysis:
        return Fail(code=404, msg="分析不存在")
    ws = await workspace_controller.check_permission(analysis.workspace_id, user_id)
    if not ws:
        return Fail(code=403, msg="无权导出")
    return make_download_response(
        path=analysis.file_path, filename=analysis.name,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


@router.post("/analysis/batch-export", summary="批量导出分析表格")
async def batch_export_analyses(req: BatchDeleteRequest):
    user_id = CTX_USER_ID.get()
    buf = io.BytesIO()
    exported = 0
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for aid in req.analysis_ids:
            analysis = await AnalysisSheet.get_or_none(id=aid)
            if not analysis:
                continue
            ws = await workspace_controller.check_permission(analysis.workspace_id, user_id)
            if not ws:
                continue
            if os.path.exists(analysis.file_path):
                # ZIP 内使用安全文件名
                safe_name = analysis.name.replace("/", "-").replace("\\", "-")
                if not safe_name.endswith(".xlsx"):
                    safe_name += ".xlsx"
                zf.write(analysis.file_path, safe_name)
                exported += 1
    if exported == 0:
        return Fail(code=404, msg="没有可导出的文件")
    buf.seek(0)
    return make_download_response(
        content=buf.getvalue(),
        filename="分析表格批量导出.zip",
        media_type="application/zip")
