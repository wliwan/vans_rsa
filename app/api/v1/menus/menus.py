import logging
import os

from fastapi import APIRouter, Query

from app.controllers.menu import menu_controller
from app.schemas.base import Fail, Success, SuccessExtra
from app.schemas.menus import *

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/list", summary="查看菜单列表")
async def list_menu(
    page: int = Query(1, description="页码"),
    page_size: int = Query(10, description="每页数量"),
):
    async def get_menu_with_children(menu_id: int):
        menu = await menu_controller.model.get(id=menu_id)
        menu_dict = await menu.to_dict()
        child_menus = await menu_controller.model.filter(parent_id=menu_id).order_by("order")
        menu_dict["children"] = [await get_menu_with_children(child.id) for child in child_menus]
        return menu_dict

    parent_menus = await menu_controller.model.filter(parent_id=0).order_by("order")
    res_menu = [await get_menu_with_children(menu.id) for menu in parent_menus]
    return SuccessExtra(data=res_menu, total=len(res_menu), page=page, page_size=page_size)


@router.get("/get", summary="查看菜单")
async def get_menu(
    menu_id: int = Query(..., description="菜单id"),
):
    result = await menu_controller.get(id=menu_id)
    return Success(data=result)


@router.post("/create", summary="创建菜单")
async def create_menu(
    menu_in: MenuCreate,
):
    await menu_controller.create(obj_in=menu_in)
    return Success(msg="Created Success")


@router.post("/update", summary="更新菜单")
async def update_menu(
    menu_in: MenuUpdate,
):
    await menu_controller.update(id=menu_in.id, obj_in=menu_in)
    return Success(msg="Updated Success")


@router.delete("/delete", summary="删除菜单")
async def delete_menu(
    id: int = Query(..., description="菜单id"),
):
    child_menu_count = await menu_controller.model.filter(parent_id=id).count()
    if child_menu_count > 0:
        return Fail(msg="Cannot delete a menu with child menus")
    await menu_controller.remove(id=id)
    return Success(msg="Deleted Success")


def _scan_views_dir(base_path: str, rel_prefix: str = "") -> list[dict]:
    """递归扫描 views 目录，返回树形结构。
    每个节点：{ path: str, name: str, children?: list }
    """
    result = []
    try:
        entries = sorted(os.listdir(base_path))
    except FileNotFoundError:
        return result

    for entry in entries:
        full = os.path.join(base_path, entry)
        if not os.path.isdir(full):
            continue
        # 跳过 __pycache__ 等特殊目录
        if entry.startswith(".") or entry.startswith("__"):
            continue
        rel_path = f"{rel_prefix}/{entry}" if rel_prefix else f"/{entry}"
        node: dict = {"path": rel_path, "name": entry}
        children = _scan_views_dir(full, rel_path)
        if children:
            node["children"] = children
        result.append(node)
    return result


@router.get("/scan-views", summary="扫描前端视图文件夹")
async def scan_views():
    """扫描 web/src/views/ 下所有子文件夹，返回树形结构供菜单配置参考。"""
    # 项目根目录相对于当前文件: app/api/v1/menus/menus.py → 项目根
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
    views_dir = os.path.join(project_root, "web", "src", "views")
    tree = _scan_views_dir(views_dir)
    return Success(data=tree)
