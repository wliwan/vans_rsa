"""路网素材 Schema"""
from typing import List, Optional

from pydantic import BaseModel, Field


class RoadMaterialCreate(BaseModel):
    """创建素材（不含文件上传，文件单独上传）"""
    name: str = Field(..., description="图片名称", example="道路鸟瞰图")
    description: Optional[str] = Field(None, description="元数据(文本)")
    region_id: int = Field(..., description="所属区域ID")
    source: str = Field("upload", description="图片来源")


class RoadMaterialUpdate(BaseModel):
    """更新素材元数据"""
    id: int
    name: Optional[str] = Field(None, description="图片名称")
    description: Optional[str] = Field(None, description="元数据(文本)")


class RoadMaterialOut(BaseModel):
    """素材输出"""
    id: int
    name: str
    description: Optional[str] = None
    region_id: int
    file_name: str
    file_path: str
    file_size: int
    width: Optional[int] = None
    height: Optional[int] = None
    color_mode: Optional[str] = None
    bit_depth: Optional[int] = None
    dpi: Optional[float] = None
    format_type: Optional[str] = None
    exif_data: Optional[dict] = None
    source: str
    short_url_token: str
    short_url: str = ""  # 须由控制器注入
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


# ── AI 处理 ──

class AIMaterialProcessRequest(BaseModel):
    """AI 图片处理请求"""
    material_ids: List[int] = Field(..., description="素材ID列表（支持批量）")
    ai_proxy_id: int = Field(..., description="AI代理ID")
    prompt: Optional[str] = Field(None, description="处理提示词（手动输入）")
    skill_id: Optional[int] = Field(None, description="Skill ID（从技能库选择）")


# ── OpenCV 处理 ──

class CVMaterialProcessRequest(BaseModel):
    """OpenCV 图片处理请求"""
    material_ids: List[int] = Field(..., description="素材ID列表（支持批量）")
    operation: str = Field(..., description="操作类型")
    params: dict = Field(default_factory=dict, description="操作参数")


# 支持的 OpenCV 操作及参数
CV_OPERATIONS = {
    # 几何变换
    "resize": {"width": "int (必填)", "height": "int (可选，等比)"},
    "rotate": {"angle": "float (必填，角度)", "scale": "float (可选，缩放)"},
    "crop": {"x": "int", "y": "int", "width": "int", "height": "int"},
    "flip": {"direction": "int (0=垂直, 1=水平, -1=两者)"},
    "border": {"top": "int", "bottom": "int", "left": "int", "right": "int",
               "color": "str (RGB hex, 如 #FF0000)"},
    # 色彩光影
    "brightness": {"value": "float (0=暗, 1=原, >1=亮)"},
    "contrast": {"value": "float (0=灰, 1=原, >1=高对比)"},
    "color_space": {"target": "str (RGB/GRAY/HSV/LAB)"},
    # 图像增强
    "blur": {"kernel_size": "int (奇数, 默认5)", "type": "str (gaussian/median/bilateral)"},
    "morphology": {"operation": "str (erode/dilate/open/close)", "kernel_size": "int", "iterations": "int"},
    "smooth": {"method": "str (bilateral/nlmeans)", "h": "int (滤波强度)", "template_window": "int", "search_window": "int"},
    "histogram_eq": {"method": "str (global/clahe)", "clip_limit": "float (CLAHE)", "tile_size": "int"},
    # 去背景
    "remove_bg": {"method": "str (grabcut/threshold)", "margin": "int"},
}
