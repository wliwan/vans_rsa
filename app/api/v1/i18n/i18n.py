"""国际化管理 API 路由"""

import logging

from fastapi import APIRouter, Query

from app.controllers.i18n import i18n_controller
from app.schemas.base import Success, SuccessExtra, Fail
from app.schemas.i18n import (
    HardcodedReplaceRequest,
    I18nAIGenerateRequest,
    I18nBatchUpdateRequest,
    I18nImportRequest,
    ScanAndAddRequest,
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


@router.get("/scan-frontend", summary="扫描前端硬编码字符串")
async def scan_frontend():
    """扫描 web/src 下前端代码中的硬编码中文字符串"""
    data = await i18n_controller.scan_frontend()
    return Success(data=data)


@router.post("/scan-and-add", summary="扫描新字段并添加")
async def scan_and_add(req: ScanAndAddRequest):
    """扫描前端硬编码中文，AI 生成 i18n key 后追加到 cn.json"""
    try:
        result = await i18n_controller.scan_and_add(
            ai_proxy_name=req.ai_proxy_name,
        )
        msg = (
            f"扫描到 {result['scanned_count']} 条新字段，"
            f"成功添加 {result['added_count']} 条，"
            f"跳过 {result['skipped_count']} 条已有字段"
        )
        return Success(data=result, msg=msg)
    except ValueError as e:
        return Fail(code=400, msg=str(e))
    except Exception as e:
        logger.exception("扫描添加失败")
        return Fail(code=500, msg=f"扫描添加失败: {e}")

@router.post("/replace-hardcoded", summary="替换前端硬编码")
async def replace_hardcoded(req: HardcodedReplaceRequest):
    """替换单个硬编码字符串为 i18n 调用"""
    result = await i18n_controller.replace_hardcoded(
        items=[req.model_dump()]
    )
    if result["errors"]:
        return Fail(code=400, msg="; ".join(result["errors"]))
    return Success(data=result, msg=f"成功替换 {result['success']} 处")