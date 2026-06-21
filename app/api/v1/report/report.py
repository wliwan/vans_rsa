import logging

from fastapi import APIRouter, Query

from app.controllers.report import report_service
from app.utils.http_utils import make_download_response
from app.core.ctx import CTX_USER_ID
from app.controllers.workspace import workspace_controller
from app.models.admin import Report
from app.schemas.base import Fail, Success, SuccessExtra
from app.schemas.reports import *

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/preview-sources", summary="预览数据源（MD转换 + 统计）")
async def preview_sources(req: ReportPreviewSources):
    try:
        result = await report_service.preview_sources(
            sheet_ids=req.sheet_ids,
            analysis_ids=req.analysis_ids,
            document_ids=req.document_ids,
            static_file_ids=req.static_file_ids,
        )
        return Success(data=result)
    except Exception as e:
        logger.exception("预览数据源失败")
        return Fail(code=500, msg=f"预览失败: {str(e)}")


@router.get("/list", summary="报告列表")
async def list_reports(
    workspace_id: int = Query(..., description="工作区ID"),
):
    user_id = CTX_USER_ID.get()
    ws = await workspace_controller.check_permission(workspace_id, user_id)
    if not ws:
        return Fail(code=403, msg="无权访问该工作区")
    reports = await Report.filter(workspace_id=workspace_id).order_by("-updated_at").all()
    data = [await r.to_dict() for r in reports]
    return Success(data=data)


@router.post("/generate", summary="生成报告")
async def generate_report(req: ReportCreate):
    user_id = CTX_USER_ID.get()
    ws = await workspace_controller.check_permission(req.workspace_id, user_id)
    if not ws:
        return Fail(code=403, msg="无权操作该工作区")
    try:
        report = await report_service.generate_report(
            workspace_id=req.workspace_id,
            name=req.name,
            sheet_ids=req.source_sheet_ids,
            analysis_ids=req.source_analysis_ids,
            ai_proxy_id=req.ai_proxy_id,
            skill_id=req.skill_id,
            extra_prompt=req.prompt,
            document_ids=req.source_document_ids,
            static_file_ids=req.source_static_ids,
        )
        return Success(data=await report.to_dict(), msg="报告生成成功")
    except Exception as e:
        logger.exception("报告生成失败")
        return Fail(code=500, msg=f"生成失败: {str(e)}")


@router.post("/update", summary="更新报告")
async def update_report(req: ReportUpdate):
    user_id = CTX_USER_ID.get()
    report = await Report.get_or_none(id=req.id)
    if not report:
        return Fail(code=404, msg="报告不存在")
    ws = await workspace_controller.check_permission(report.workspace_id, user_id)
    if not ws:
        return Fail(code=403, msg="无权操作")
    update_data = req.model_dump(exclude_unset=True, exclude={"id"})
    if update_data:
        await report.update_from_dict(update_data).save()
    return Success(data=await report.to_dict(), msg="更新成功")


@router.post("/clone", summary="克隆报告")
async def clone_report(req: ReportClone):
    user_id = CTX_USER_ID.get()
    source = await Report.get_or_none(id=req.id)
    if not source:
        return Fail(code=404, msg="源报告不存在")
    ws = await workspace_controller.check_permission(source.workspace_id, user_id)
    if not ws:
        return Fail(code=403, msg="无权操作")
    new_report = await Report.create(
        workspace_id=source.workspace_id,
        name=req.name,
        content=source.content,
        source_sheet_ids=source.source_sheet_ids,
        source_analysis_ids=source.source_analysis_ids,
        source_document_ids=source.source_document_ids,
        source_static_ids=source.source_static_ids,
        ai_proxy_id=source.ai_proxy_id,
        skill_id=source.skill_id,
        prompt=source.prompt,
    )
    return Success(data=await new_report.to_dict(), msg="克隆成功")


@router.delete("/delete", summary="删除报告")
async def delete_report(report_id: int = Query(..., description="报告ID")):
    user_id = CTX_USER_ID.get()
    report = await Report.get_or_none(id=report_id)
    if not report:
        return Fail(code=404, msg="报告不存在")
    ws = await workspace_controller.check_permission(report.workspace_id, user_id)
    if not ws:
        return Fail(code=403, msg="无权操作")
    await report.delete()
    return Success(msg="删除成功")


@router.get("/get", summary="获取报告内容")
async def get_report(report_id: int = Query(..., description="报告ID")):
    user_id = CTX_USER_ID.get()
    report = await Report.get_or_none(id=report_id)
    if not report:
        return Fail(code=404, msg="报告不存在")
    ws = await workspace_controller.check_permission(report.workspace_id, user_id)
    if not ws:
        return Fail(code=403, msg="无权访问")
    return Success(data=await report.to_dict())


# ==================== 导出 ====================

def _check_report_permission(report, user_id):
    async def _check():
        return await workspace_controller.check_permission(report.workspace_id, user_id)
    return _check


@router.get("/export/html", summary="导出HTML")
async def export_html(report_id: int = Query(...)):
    user_id = CTX_USER_ID.get()
    report = await Report.get_or_none(id=report_id)
    if not report:
        return Fail(code=404, msg="报告不存在")
    ws = await workspace_controller.check_permission(report.workspace_id, user_id)
    if not ws:
        return Fail(code=403, msg="无权导出")
    html = await report_service.export_html(report_id)
    return make_download_response(
        content=html.encode("utf-8"),
        filename=f"{report.name}.html",
        media_type="text/html; charset=utf-8")


@router.get("/export/pdf", summary="导出PDF")
async def export_pdf(report_id: int = Query(...)):
    user_id = CTX_USER_ID.get()
    report = await Report.get_or_none(id=report_id)
    if not report:
        return Fail(code=404, msg="报告不存在")
    ws = await workspace_controller.check_permission(report.workspace_id, user_id)
    if not ws:
        return Fail(code=403, msg="无权导出")
    try:
        pdf_bytes = await report_service.export_pdf_bytes(report_id)
        return make_download_response(
            content=pdf_bytes, filename=f"{report.name}.pdf",
            media_type="application/pdf")
    except Exception as e:
        return Fail(code=500, msg=f"PDF导出失败: {str(e)}")


@router.get("/export/docx", summary="导出Word")
async def export_docx(report_id: int = Query(...)):
    user_id = CTX_USER_ID.get()
    report = await Report.get_or_none(id=report_id)
    if not report:
        return Fail(code=404, msg="报告不存在")
    ws = await workspace_controller.check_permission(report.workspace_id, user_id)
    if not ws:
        return Fail(code=403, msg="无权导出")
    try:
        docx_bytes = await report_service.export_docx_bytes(report_id)
        return make_download_response(
            content=docx_bytes,
            filename=f"{report.name}.docx",
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
    except Exception as e:
        return Fail(code=500, msg=f"Word导出失败: {str(e)}")
