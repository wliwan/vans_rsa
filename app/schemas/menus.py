from enum import StrEnum
from typing import Optional

from pydantic import BaseModel, Field


class MenuType(StrEnum):
    CATALOG = "catalog"  # 目录
    MENU = "menu"  # 菜单


class BaseMenu(BaseModel):
    id: int
    name: str
    path: str
    remark: Optional[dict]
    menu_type: Optional[MenuType]
    icon: Optional[str]
    order: int
    parent_id: int
    is_hidden: bool
    component: str
    keepalive: bool
    redirect: Optional[str]
    children: Optional[list["BaseMenu"]]


class MenuCreate(BaseModel):
    menu_type: MenuType = Field(default=MenuType.CATALOG.value)
    name: str = Field(example="用户管理")
    icon: Optional[str] = "ph:user-list-bold"
    path: str = Field(example="/system/user")
    order: Optional[int] = Field(example=1)
    parent_id: Optional[int] = Field(example=0, default=0)
    is_hidden: Optional[bool] = False
    component: str = Field(default="Layout", example="/system/user")
    keepalive: Optional[bool] = True
    redirect: Optional[str] = ""


class MenuUpdate(BaseModel):
    id: int
    menu_type: Optional[MenuType] = Field(example=MenuType.CATALOG.value)
    name: Optional[str] = Field(example="用户管理")
    icon: Optional[str] = "ph:user-list-bold"
    path: Optional[str] = Field(example="/system/user")
    order: Optional[int] = Field(example=1)
    parent_id: Optional[int] = Field(example=0)
    is_hidden: Optional[bool] = False
    component: str = Field(example="/system/user")
    keepalive: Optional[bool] = False
    redirect: Optional[str] = ""


# --- AI 智能视图 ---


class MenuAIAnalyzeRequest(BaseModel):
    """AI 智能分析请求"""
    proxy_name: str = Field(..., description="AI代理名称")
    extra_prompt: str = Field(default="", description="额外提示词")


class AIMenuNode(BaseModel):
    """AI 生成的菜单节点（用于前端预览和编辑，不含 id/parent_id）"""
    name: str = Field(..., description="菜单名称")
    menu_type: MenuType = Field(default=MenuType.CATALOG, description="菜单类型")
    icon: Optional[str] = Field(default="ph:folder-duotone", description="图标")
    order: int = Field(default=1, description="排序")
    path: str = Field(..., description="访问路径")
    redirect: Optional[str] = Field(default="", description="跳转路径")
    component: str = Field(default="Layout", description="组件路径")
    keepalive: bool = Field(default=True, description="保活")
    is_hidden: bool = Field(default=False, description="隐藏")
    view_path: Optional[str] = Field(default="", description="原始扫描路径")
    children: Optional[list["AIMenuNode"]] = Field(default=None, description="子菜单")


class MenuAIAnalyzeResponse(BaseModel):
    """AI 分析响应：包含扫描树和 AI 生成的菜单结构"""
    scan_tree: list[dict] = Field(default_factory=list, description="views 目录扫描树")
    menu_tree: list[AIMenuNode] = Field(default_factory=list, description="AI 生成的菜单树")


class MenuBatchSaveRequest(BaseModel):
    """批量保存菜单：递归结构，服务端先清空旧菜单再重建"""
    menu_tree: list[AIMenuNode] = Field(..., description="完整菜单树")
