import asyncio
import json
import logging
import os
import re

from fastapi import APIRouter, Query, UploadFile, File
from fastapi.responses import StreamingResponse
from io import BytesIO

from app.controllers.menu import menu_controller
from app.core.ctx import CTX_USER_ID
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


def _scan_views_recursive(base_path: str, rel_prefix: str = "") -> list[str]:
    """递归扫描 views 目录，返回所有子目录的相对路径列表（扁平）。"""
    result = []
    try:
        entries = sorted(os.listdir(base_path))
    except FileNotFoundError:
        return result

    for entry in entries:
        full = os.path.join(base_path, entry)
        if not os.path.isdir(full):
            continue
        if entry.startswith(".") or entry.startswith("__"):
            continue
        rel_path = f"{rel_prefix}/{entry}" if rel_prefix else f"/{entry}"
        result.append(rel_path)
        result.extend(_scan_views_recursive(full, rel_path))
    return result


def _get_views_dir() -> str:
    """获取 web/src/views/ 绝对路径"""
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
    return os.path.join(project_root, "web", "src", "views")


@router.get("/scan-views", summary="扫描前端视图文件夹")
async def scan_views():
    """扫描 web/src/views/ 下所有子文件夹，返回树形结构供菜单配置参考。"""
    views_dir = _get_views_dir()
    tree = _scan_views_dir(views_dir)
    return Success(data=tree)


# ---------------------------------------------------------------------------
# AI 智能视图
# ---------------------------------------------------------------------------


def _build_scan_tree_description(tree: list[dict], indent: int = 0) -> str:
    """将扫描树转为缩进文本描述，供 AI 理解视图目录结构。"""
    lines = []
    prefix = "  " * indent
    for node in tree:
        lines.append(f"{prefix}- {node['path']} (目录名: {node['name']})")
        if "children" in node and node["children"]:
            lines.append(_build_scan_tree_description(node["children"], indent + 1))
    return "\n".join(lines)


def _build_system_prompt(scan_tree: list[dict], all_paths: list[str], extra_prompt: str, current_menu_json: str = "") -> str:
    """构建 AI 调用的 system prompt"""
    tree_desc = _build_scan_tree_description(scan_tree)
    paths_list = "\n".join(all_paths)

    current_menu_section = ""
    if current_menu_json:
        current_menu_section = f"""
## 当前已有菜单（请在此基础上增量调整，保留用户已有的自定义设置）
```json
{current_menu_json}
```
"""

    prompt = f"""你是一个 Vue 前端项目的菜单配置专家。请根据 views 目录结构和当前已有菜单，生成调整后的路由菜单配置。

## 项目背景
- 技术栈: Vue 3 + Naive UI + Vite
- 路由模式: 后端动态路由 + RBAC
- 组件路径前缀以 "/" 开头，如 "/system/user" 表示 web/src/views/system/user/index.vue
- 一级菜单（最顶层）component 填 "Layout"，子菜单填实际的组件路径

## views 目录树形结构
{tree_desc}

## 所有视图路径（扁平列表）
{paths_list}
{current_menu_section}
## 菜单字段说明
- menu_type: "catalog"(目录/分组,无实际页面) 或 "menu"(具体页面,对应于views下的文件夹)
- name: 中文菜单名称（根据目录名推断，如 "system"→"系统管理", "user"→"用户管理", "workbench"→"工作台"）
- icon: 使用 Iconify 图标名称（如 "ph:gear-duotone" 表示系统设置），请根据功能选择合适图标。常用图标参考:
  系统管理类: ph:gear-duotone, ph:wrench-duotone
  用户/角色类: ph:user-list-bold, ph:users-duotone, ph:shield-check-duotone
  文档类: ph:file-text-duotone, ph:files-duotone
  数据/表格类: ph:table-duotone, ph:database-duotone
  工具类: ph:toolbox-duotone, ph:hammer-duotone
  工作台: ph:desktop-duotone, ph:monitor-duotone
  地图/位置: ph:map-pin-duotone, ph:globe-duotone
  图片/媒体: ph:image-duotone, ph:camera-duotone
  网络/通信: ph:wifi-high-duotone, ph:broadcast-duotone
  统计/图表: ph:chart-bar-duotone, ph:chart-line-duotone
  配置/设置: ph:sliders-duotone, ph:gear-six-duotone
  菜单/导航: ph:list-bullets-duotone, ph:squares-four-duotone
  其他通用: ph:folder-duotone, ph:package-duotone
- order: 排序号（从1开始递增，每级独立）
- path: 访问路径，格式 "/一级/二级"，如 "/system/user"。确保与目录层级对应。
- redirect: 跳转路径，只有一级目录菜单可填写（有子菜单时填写第一个子菜单路径），普通菜单留空 ""
- component: 一级目录填 "Layout"，子菜单填对应视图的相对路径 "/xxx/yyy"
- keepalive: 是否保活，列表/表单类页面填 true，统计/大屏类填 false
- is_hidden: 是否隐藏，普通菜单填 false，特殊隐藏页面（如 login, error-page）填 true

## 增量调整原则（非常重要）
{'''1. **保留现有配置**：对于 views 目录中仍然存在的页面，优先保留当前菜单中已有的 name、icon、order、keepalive、is_hidden 等用户已自定义的字段，不要随意改动
2. **新增缺失菜单**：views 中有但当前菜单中不存在的目录，自动生成合理的菜单项
3. **移除过时菜单**：当前菜单中存在但 views 中已不存在的项应移除
4. **路径匹配**：通过 path 字段来关联 views 目录和当前菜单项（如 views 的 /system/user 对应菜单 path="/system/user"）
5. **仅在新项上自动生成**：只有新增的菜单项才需要自动推断中文名和图标，已有项保持用户设置''' if current_menu_json else '''1. 根据目录名称推断合理的菜单名称（中文），不要直接用英文目录名作为菜单名
2. 每个 views 下的叶子目录（没有子目录的）一般对应一个 menu_type="menu" 的菜单项
3. 有子目录的上层目录对应 menu_type="catalog" 的目录菜单
4. login、error-page 等非业务页面设为隐藏 (is_hidden=true)
5. 按功能分组排序，系统管理类在前，业务功能在后
6. 每级菜单 order 从 1 开始递增'''}

## 额外提示词
{extra_prompt if extra_prompt else "（无）"}

## 输出格式
请严格输出 JSON，格式如下，不要包含任何其他文字或 markdown 代码块标记:
{{
  "menu_tree": [
    {{
      "name": "系统管理",
      "menu_type": "catalog",
      "icon": "ph:gear-duotone",
      "order": 1,
      "path": "/system",
      "redirect": "/system/user",
      "component": "Layout",
      "keepalive": true,
      "is_hidden": false,
      "children": [
        {{
          "name": "用户管理",
          "menu_type": "menu",
          "icon": "ph:user-list-bold",
          "order": 1,
          "path": "/system/user",
          "redirect": "",
          "component": "/system/user",
          "keepalive": true,
          "is_hidden": false
        }}
      ]
    }}
  ]
}}
"""
    return prompt


def _extract_menu_json(text: str) -> dict | None:
    """多策略提取 JSON — 参考 skills.py 的实现"""
    # 策略1: 直接解析
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 策略2: 提取 ```json ... ``` 块
    m = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            pass

    # 策略3: 找到第一个 { 和最后一个 } 配对
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(text[start:end + 1])
        except json.JSONDecodeError:
            pass

    return None


@router.post("/ai-analyze-views", summary="AI智能分析视图生成菜单")
async def ai_analyze_views(req: MenuAIAnalyzeRequest):
    """扫描 views 目录 + 调用 AI 分析生成菜单配置"""
    from app.controllers.ai_proxy import ai_proxy_controller

    user_id = CTX_USER_ID.get()

    # 1. 权限检查
    ai_proxy = await ai_proxy_controller.check_permission_by_name(name=req.proxy_name, user_id=user_id)
    if not ai_proxy:
        return Fail(code=403, msg="无权使用该AI代理或代理不存在")

    # 2. 扫描 views 目录
    views_dir = _get_views_dir()
    scan_tree = _scan_views_dir(views_dir)
    all_paths = _scan_views_recursive(views_dir)

    # 2.5 获取当前已有菜单（导出格式，作为 AI 的增量调整基础）
    current_menu_json = ""
    try:
        from app.models.admin import Menu

        async def _get_menu_tree(parent_id: int = 0):
            menus = await Menu.filter(parent_id=parent_id).order_by("order")
            result = []
            for m in menus:
                d = await m.to_dict()
                children = await _get_menu_tree(m.id)
                if children:
                    d["children"] = children
                result.append(d)
            return result

        raw_tree = await _get_menu_tree(parent_id=0)
        if raw_tree:
            export_tree = [_menu_to_export_node(n) for n in raw_tree]
            current_menu_json = json.dumps(export_tree, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.warning(f"获取当前菜单失败，将以空菜单模式运行: {e}")

    # 3. 构建 prompt 并调用 AI
    system_prompt = _build_system_prompt(scan_tree, all_paths, req.extra_prompt, current_menu_json)
    max_tokens = ai_proxy.max_tokens or 16384

    from openai import OpenAI

    client = OpenAI(base_url=ai_proxy.url, api_key=ai_proxy.token)
    model = ai_proxy.model or "gpt-4"

    def _sync_call():
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": "请根据上述 views 目录结构生成完整的菜单配置 JSON。"},
            ],
            max_tokens=max_tokens,
            temperature=0.3,
        )
        return response.choices[0].message.content

    ai_response = await asyncio.to_thread(_sync_call)
    logger.info(f"AI菜单分析原始响应(前500字): {ai_response[:500]}")

    # 4. 解析 AI 响应
    result = _extract_menu_json(ai_response)
    if result is None:
        logger.warning(f"AI菜单分析JSON解析失败，完整响应: {ai_response}")
        return Fail(code=500, msg="AI生成内容格式异常，请重试")

    menu_tree_raw = result.get("menu_tree", []) if isinstance(result, dict) else []

    # 5. 补全 view_path 字段（根据 path 自动匹配）
    def enrich_view_path(nodes: list[dict], parent_path: str = ""):
        enriched = []
        for node in nodes:
            node.setdefault("view_path", node.get("path", ""))
            if "children" in node and node["children"]:
                node["children"] = enrich_view_path(node["children"], node["path"])
            enriched.append(node)
        return enriched

    menu_tree_raw = enrich_view_path(menu_tree_raw)

    # 6. 返回扫描树 + AI 菜单树
    return Success(data={
        "scan_tree": scan_tree,
        "menu_tree": menu_tree_raw,
    })


async def _reset_menu_auto_increment():
    """重置 SQLite menu 表的自增 ID 计数器（DELETE 不会自动重置 AUTOINCREMENT）"""
    import logging
    _log = logging.getLogger(__name__)
    try:
        from app.models.admin import Menu
        db = Menu._meta.db
        if db:
            await db.execute_query("DELETE FROM sqlite_sequence WHERE name='menu'")
            result = await db.execute_query("INSERT INTO sqlite_sequence VALUES ('menu', 0)")
            _log.info(f"重置 menu 自增 ID 完成: {result}")
    except Exception as e:
        _log.warning(f"重置 menu 自增 ID 失败: {e}")


@router.post("/batch-save", summary="批量保存菜单（清空后重建）")
async def batch_save_menus(req: MenuBatchSaveRequest):
    """接收完整菜单树，清空旧菜单后一次性重建整个菜单表。"""
    from app.models.admin import Menu

    async def _save_node(node: AIMenuNode, parent_id: int = 0) -> int:
        """递归保存节点并返回新 id"""
        menu = await Menu.create(
            name=node.name,
            menu_type=node.menu_type,
            icon=node.icon,
            order=node.order,
            path=node.path,
            parent_id=parent_id,
            is_hidden=node.is_hidden,
            component=node.component,
            keepalive=node.keepalive,
            redirect=node.redirect or "",
        )
        new_id = menu.id
        if node.children:
            for child in node.children:
                await _save_node(child, parent_id=new_id)
        return new_id

    # 1. 清空所有旧菜单并重置自增 ID
    await Menu.all().delete()
    await _reset_menu_auto_increment()

    # 2. 重建
    count = 0
    for node in req.menu_tree:
        await _save_node(node, parent_id=0)
        count += 1

    logger.info(f"批量菜单保存完成，共 {count} 个一级菜单")
    return Success(msg=f"菜单已重建，共 {count} 个一级菜单")


# ---------------------------------------------------------------------------
# 导出 / 导入
# ---------------------------------------------------------------------------


def _menu_to_export_node(menu_dict: dict) -> dict:
    """将数据库菜单记录转为导出格式（去除 id/parent_id/时间戳等内部字段）"""
    node = {
        "name": menu_dict.get("name", ""),
        "menu_type": menu_dict.get("menu_type", "catalog"),
        "icon": menu_dict.get("icon") or "",
        "order": menu_dict.get("order", 1),
        "path": menu_dict.get("path", ""),
        "redirect": menu_dict.get("redirect") or "",
        "component": menu_dict.get("component", "Layout"),
        "keepalive": menu_dict.get("keepalive", True),
        "is_hidden": menu_dict.get("is_hidden", False),
    }
    children = menu_dict.get("children", [])
    if children:
        node["children"] = [_menu_to_export_node(c) for c in children]
    return node


@router.get("/export", summary="导出菜单为JSON文件")
async def export_menus():
    """导出当前全部菜单树为 JSON 文件下载"""
    from app.models.admin import Menu

    async def get_menu_tree(parent_id: int = 0):
        menus = await Menu.filter(parent_id=parent_id).order_by("order")
        result = []
        for m in menus:
            d = await m.to_dict()
            children = await get_menu_tree(m.id)
            if children:
                d["children"] = children
            result.append(d)
        return result

    raw_tree = await get_menu_tree(parent_id=0)
    export_tree = [_menu_to_export_node(n) for n in raw_tree]
    json_bytes = json.dumps(export_tree, ensure_ascii=False, indent=2).encode("utf-8")

    return StreamingResponse(
        BytesIO(json_bytes),
        media_type="application/json",
        headers={"Content-Disposition": "attachment; filename=menu-export.json"},
    )


@router.post("/import", summary="导入菜单JSON文件（替换当前设置）")
async def import_menus(file: UploadFile = File(..., description="菜单JSON文件")):
    """上传 JSON 文件，清空旧菜单后重建"""
    from app.models.admin import Menu

    # 1. 读取并解析 JSON
    raw = await file.read()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return Fail(code=400, msg="JSON 格式错误，无法解析")

    if not isinstance(data, list):
        return Fail(code=400, msg="JSON 格式错误：应为菜单数组")

    # 2. 递归保存
    async def _save_import_node(node: dict, parent_id: int = 0) -> None:
        menu = await Menu.create(
            name=node.get("name", "未命名"),
            menu_type=node.get("menu_type", "catalog"),
            icon=node.get("icon") or None,
            order=node.get("order", 1),
            path=node.get("path", "/"),
            parent_id=parent_id,
            is_hidden=node.get("is_hidden", False),
            component=node.get("component", "Layout"),
            keepalive=node.get("keepalive", True),
            redirect=node.get("redirect") or "",
        )
        children = node.get("children", [])
        if children:
            for child in children:
                await _save_import_node(child, parent_id=menu.id)

    # 3. 清空 + 重建（重置自增 ID）
    await Menu.all().delete()
    await _reset_menu_auto_increment()
    count = 0
    for node in data:
        await _save_import_node(node)
        count += 1

    logger.info(f"菜单导入完成，共 {count} 个一级菜单")
    return Success(msg=f"菜单已导入，共 {count} 个一级菜单")