"""菜单国际化管理 API 路由"""

import logging

from fastapi import APIRouter, Query, Body

from app.controllers.menu import menu_i18n_controller
from app.schemas.base import Success, Fail
from app.schemas.menus import (
    MenuI18nSaveRequest,
    MenuI18nAIGenerateRequest,
    MenuI18nImportRequest,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/list", summary="查看菜单国际化列表")
async def list_menu_i18n(
    locale: str = Query("", description="语言代码，为空时返回所有语言"),
):
    """列出所有菜单的国际化翻译数据"""
    data = await menu_i18n_controller.get_list(locale=locale)
    return Success(data=data)


@router.post("/save", summary="保存菜单翻译")
async def save_menu_i18n(req: MenuI18nSaveRequest):
    """保存/更新单条菜单翻译"""
    try:
        result = await menu_i18n_controller.save(
            menu_id=req.menu_id, locale=req.locale, name=req.name
        )
        return Success(data=result, msg="保存成功")
    except ValueError as e:
        return Fail(code=400, msg=str(e))


@router.delete("/delete", summary="删除菜单翻译")
async def delete_menu_i18n(
    menu_id: int = Query(..., description="菜单ID"),
    locale: str = Query(..., description="语言代码"),
):
    """删除指定菜单在指定语言下的翻译"""
    ok = await menu_i18n_controller.delete(menu_id=menu_id, locale=locale)
    if ok:
        return Success(msg="删除成功")
    return Fail(code=404, msg="未找到该翻译记录")


@router.post("/ai-generate", summary="AI翻译菜单名称")
async def ai_generate_menu_i18n(req: MenuI18nAIGenerateRequest):
    """使用 AI 代理将菜单名称翻译为目标语言"""
    try:
        result = await menu_i18n_controller.ai_generate(
            proxy_name=req.proxy_name,
            target_locales=req.target_locales,
            mode=req.mode,
        )
        return Success(data=result, msg="AI 翻译完成")
    except ValueError as e:
        return Fail(code=400, msg=str(e))
    except Exception as e:
        logger.exception("AI 菜单翻译失败")
        return Fail(code=500, msg=f"AI 翻译失败: {e}")


@router.get("/export", summary="导出菜单翻译")
async def export_menu_i18n(
    locale: str = Query(..., description="语言代码"),
):
    """导出指定语言的菜单翻译数据"""
    data = await menu_i18n_controller.export_data(locale=locale)
    return Success(data=data)


@router.post("/import", summary="导入菜单翻译")
async def import_menu_i18n(req: MenuI18nImportRequest):
    """导入指定语言的菜单翻译数据"""
    try:
        count = await menu_i18n_controller.import_data(
            locale=req.locale, entries=req.entries
        )
        return Success(data={"count": count}, msg=f"成功导入 {count} 条翻译")
    except Exception as e:
        logger.exception("导入菜单翻译失败")
        return Fail(code=500, msg=f"导入失败: {e}")
