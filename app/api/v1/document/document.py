import io
import logging
import os
import zipfile
from typing import List

from fastapi import APIRouter, File, Query, UploadFile
from fastapi.responses import FileResponse
from tortoise.expressions import Q

from app.controllers.document import document_controller
from app.controllers.workspace import workspace_controller
from app.core.ctx import CTX_USER_ID
from app.models.admin import Document
from app.schemas.base import Fail, Success, SuccessExtra
from app.schemas.documents import DocumentAIAnalyze, DocumentBatchDelete, DocumentBatchExport, DocumentCreateText, DocumentImportFromSurvey, DocumentUpdateContent
from app.utils.http_utils import make_download_response

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/list", summary="查看文档列表")
async def list_documents(
    workspace_id: int = Query(..., description="工作区ID"),
    source_type: str = Query(None, description="文档类型: original / analysis"),
):
    docs = await document_controller.list_by_workspace(workspace_id, source_type)
    data = [await d.to_dict() for d in docs]
    return SuccessExtra(data=data, total=len(data), page=1, page_size=len(data))


@router.post("/upload", summary="上传文档")
async def upload_document(
    workspace_id: int = Query(..., description="工作区ID"),
    file: UploadFile = None,
):
    try:
        doc = await document_controller.upload(workspace_id, file)
        return Success(data=await doc.to_dict(), msg="上传成功")
    except ValueError as e:
        return Fail(code=400, msg=str(e))
    except Exception as e:
        logger.error(f"上传文档失败: {e}")
        return Fail(code=500, msg="上传失败")


@router.post("/batch-upload", summary="批量上传文档")
async def batch_upload_documents(
    workspace_id: int = Query(..., description="工作区ID"),
    files: List[UploadFile] = File(..., description="文档文件列表"),
):
    success_list, error_list = [], []
    for file in files:
        try:
            doc = await document_controller.upload(workspace_id, file)
            success_list.append(await doc.to_dict())
        except ValueError as e:
            error_list.append({"filename": file.filename or "未知", "reason": str(e)})
        except Exception as e:
            logger.warning(f"批量上传文档失败 [{file.filename}]: {e}")
            error_list.append({"filename": file.filename or "未知", "reason": str(e)})
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


@router.get("/download", summary="下载文档")
async def download_document(
    document_id: int = Query(..., description="文档ID"),
):
    doc = await document_controller.get(document_id)
    if not doc:
        return Fail(code=404, msg="文档不存在")
    if not os.path.exists(doc.file_path):
        return Fail(code=404, msg="文件不存在")
    filename = doc.name
    if doc.file_path.endswith('.md') and not filename.endswith('.md'):
        filename += '.md'
    return FileResponse(doc.file_path, filename=filename, media_type="application/octet-stream")


@router.delete("/delete", summary="删除文档")
async def delete_document(
    document_id: int = Query(..., description="文档ID"),
):
    await document_controller.delete(document_id)
    return Success(msg="删除成功")


@router.post("/batch-delete", summary="批量删除文档")
async def batch_delete_documents(body: DocumentBatchDelete):
    await document_controller.batch_delete(body.document_ids)
    return Success(msg=f"已删除 {len(body.document_ids)} 个文档")


@router.post("/batch-export", summary="批量导出文档")
async def batch_export_documents(body: DocumentBatchExport):
    user_id = CTX_USER_ID.get()
    buf = io.BytesIO()
    exported = 0
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for did in body.document_ids:
            doc = await Document.filter(id=did).first()
            if not doc:
                continue
            ws = await workspace_controller.check_permission(doc.workspace_id, user_id)
            if not ws:
                continue
            if os.path.exists(doc.file_path):
                zf.write(doc.file_path, doc.name)
                exported += 1
    if exported == 0:
        return Fail(code=404, msg="没有可导出的文件")
    buf.seek(0)
    return make_download_response(
        content=buf.getvalue(),
        filename="文档批量导出.zip",
        media_type="application/zip")


@router.delete("/clear", summary="清空工作区文档")
async def clear_documents(
    workspace_id: int = Query(..., description="工作区ID"),
):
    await document_controller.clear_by_workspace(workspace_id)
    return Success(msg="已清空")


@router.post("/ai-analyze", summary="AI分析文档")
async def ai_analyze_documents(body: DocumentAIAnalyze):
    try:
        analysis_doc = await document_controller.ai_analyze(
            workspace_id=body.workspace_id,
            document_ids=body.document_ids,
            ai_proxy_id=body.ai_proxy_id,
            skill_id=body.skill_id,
            prompt=body.prompt or "",
        )
        return Success(data=await analysis_doc.to_dict(), msg="分析完成")
    except ValueError as e:
        return Fail(code=400, msg=str(e))
    except Exception as e:
        logger.error(f"AI分析失败: {e}")
        return Fail(code=500, msg="分析失败")


@router.post("/create-text", summary="从文本创建文档")
async def create_document_from_text(body: DocumentCreateText):
    try:
        doc = await document_controller.create_from_text(body.workspace_id, body.name, body.content)
        return Success(data=await doc.to_dict(), msg="创建成功")
    except Exception as e:
        logger.error(f"创建文档失败: {e}")
        return Fail(code=500, msg="创建失败")


@router.get("/get-content", summary="获取文档内容")
async def get_document_content(
    document_id: int = Query(..., description="文档ID"),
):
    content = await document_controller.get_content(document_id)
    if content is None:
        return Fail(code=404, msg="文档不存在或无法读取")
    return Success(data={"content": content})


@router.post("/update-content", summary="更新文档内容")
async def update_document_content(body: DocumentUpdateContent):
    doc = await document_controller.update_content(body.document_id, body.content, body.name)
    if doc is None:
        return Fail(code=404, msg="文档不存在")
    return Success(data=await doc.to_dict(), msg="保存成功")


@router.post("/import-from-survey", summary="从问卷导入文档")
async def import_from_survey(body: DocumentImportFromSurvey):
    """将问卷提交记录（JSON）转换为 Markdown 文档，保存到指定工作区的原始文档列表"""
    try:
        doc = await document_controller.import_from_survey(body.workspace_id, body.submission_id)
        return Success(data=await doc.to_dict(), msg="导入成功")
    except ValueError as e:
        return Fail(code=400, msg=str(e))
    except Exception as e:
        logger.error(f"从问卷导入文档失败: {e}")
        return Fail(code=500, msg="导入失败")
