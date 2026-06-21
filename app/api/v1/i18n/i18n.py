"""国际化管理 API 路由"""

import logging
from typing import List

from fastapi import APIRouter, Query, Body

from app.controllers.i18n import i18n_controller
from app.schemas.base import Success, SuccessExtra, Fail
from app.schemas.i18n import (
    I18nAIGenerateRequest,
    I18nBatchUpdateRequest,
    I18nImportRequest,
    I18nBatchDeleteRequest,
    ProcessScanRequest,
    I18nUpdateRequest,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/list", summary="查看国际化翻译列表")
async def list_i18n():
    """列出所有语言的国际化条目"""
    data = await i18n_controller.get_list()
    return Success(data=data)


@router.put("/update", summary="更新单条翻译")
async def update_i18n(update_in: I18nUpdateRequest):
    """更新指定语言下的单个翻译字段"""
    ok = await i18n_controller.update(
        key=update_in.key, locale=update_in.locale, value=update_in.value
    )
    if ok:
        return Success(msg="更新成功")
    return Fail(code=400, msg="更新失败，可能该语言文件不存在")


@router.put("/batch-update", summary="批量更新翻译")
async def batch_update_i18n(update_in: I18nBatchUpdateRequest):
    """批量更新多条翻译"""
    updates = [(u.key, u.locale, u.value) for u in update_in.updates]
    count = await i18n_controller.batch_update(updates)
    return Success(data={"count": count}, msg=f"成功更新 {count} 条")


@router.get("/export", summary="导出所有国际化数据")
async def export_i18n():
    """导出所有语言翻译数据为 JSON"""
    data = await i18n_controller.export_data()
    return Success(data=data)


@router.post("/import", summary="导入国际化数据")
async def import_i18n(import_in: I18nImportRequest):
    """导入指定语言的完整翻译 JSON"""
    await i18n_controller.import_data(
        locale=import_in.locale, data=import_in.data
    )
    return Success(msg=f"语言 {import_in.locale} 导入成功")


@router.post("/ai-generate", summary="AI翻译")
async def ai_generate_i18n(req: I18nAIGenerateRequest):
    """使用 AI 代理将中文翻译为目标语言"""
    try:
        result = await i18n_controller.ai_generate(
            ai_proxy_name=req.ai_proxy_name,
            target_locale=req.target_locale,
            mode=req.mode,
        )
        return Success(data=result, msg="AI 翻译完成")
    except ValueError as e:
        return Fail(code=400, msg=str(e))
    except Exception as e:
        logger.exception("AI 翻译失败")
        return Fail(code=500, msg=f"AI 翻译失败: {e}")


@router.get(
    "/scan-new-fields",
    summary="扫描前端代码中的硬编码中文字符串（Python 正则，不依赖 npm 包）",
)
async def scan_new_fields():
    """扫描 web/src/ 下所有 .vue/.js/.ts/.jsx/.tsx 文件，提取未国际化的硬编码中文"""
    try:
        result = await i18n_controller.scan_frontend()
        return Success(data=result, msg=f"扫描完成，发现 {result['total']} 条待翻译字段")
    except Exception as e:
        logger.exception("scan_new_fields 失败")
        return Fail(code=500, msg=f"扫描失败: {e}")


@router.post("/process-scan", summary="处理前端扫描结果并添加")
async def process_scan(req: ProcessScanRequest):
    """接收扫描结果，AI 生成 i18n key 后追加到 cn.json（可选安全模式不写源文件）"""
    try:
        result = await i18n_controller.process_scan(
            ai_proxy_name=req.ai_proxy_name,
            items=req.items,
            safe_mode=req.safe_mode,
        )
        msg = (
            f"扫描到 {result['scanned_count']} 条新字段，"
            f"成功添加 {result['added_count']} 条"
        )
        if result.get("replaced_count"):
            msg += f"，已替换源文件 {result['replaced_count']} 处"
        return Success(data=result, msg=msg)
    except ValueError as e:
        return Fail(code=400, msg=str(e))
    except Exception as e:
        logger.exception("process_scan 失败")
        return Fail(code=500, msg=f"处理失败: {e}")


@router.post("/verify-build", summary="验证前端编译（pnpm build）")
async def verify_build():
    """运行 pnpm build 检查前端编译是否通过"""
    try:
        result = i18n_controller._verify_frontend_build()
        if result["ok"]:
            return Success(data=result, msg="编译通过")
        else:
            return Fail(code=400, msg=f"编译失败 (exit={result['exit_code']})", data=result)
    except Exception as e:
        logger.exception("verify_build 失败")
        return Fail(code=500, msg=f"编译验证异常: {e}")


@router.post("/git-restore", summary="Git 回退指定文件")
async def git_restore(files: List[str] = Body(..., embed=True)):
    """用 git checkout HEAD -- <file> 回退指定文件"""
    if not files:
        return Fail(code=400, msg="未指定要回退的文件")
    try:
        ok = i18n_controller._git_restore_files(files)
        return Success(data={"ok": ok, "files": files}, msg="回退完成" if ok else "部分回退失败")
    except Exception as e:
        logger.exception("git_restore 失败")
        return Fail(code=500, msg=f"回退异常: {e}")


@router.get("/git-modified-files", summary="获取 Git 已修改未暂存的文件列表")
async def git_modified_files():
    """获取 git diff --name-only 的文件列表"""
    try:
        files = i18n_controller._git_modified_files()
        return Success(data={"files": files, "count": len(files)})
    except Exception as e:
        return Fail(code=500, msg=f"获取失败: {e}")


@router.post("/batch-delete", summary="批量删除国际化字段")
async def batch_delete_i18n(req: I18nBatchDeleteRequest):
    """从所有语言文件中批量删除指定 key 及其值"""
    try:
        result = await i18n_controller.batch_delete(keys=req.keys)
        return Success(data=result, msg=f"成功删除 {result['deleted']} 个字段")
    except Exception as e:
        logger.exception("批量删除失败")
        return Fail(code=500, msg=f"批量删除失败: {e}")