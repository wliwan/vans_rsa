"""静态文件数据 Schema"""
from typing import List, Optional

from pydantic import BaseModel, Field


class StaticFileCreate(BaseModel):
    """创建静态文件（不含文件上传）"""
    name: str = Field(..., description="文件名称")
    description: Optional[str] = Field(None, description="元数据(文本)")


class StaticFileUpdate(BaseModel):
    """更新静态文件元数据"""
    id: int
    name: Optional[str] = Field(None, description="文件名称")
    description: Optional[str] = Field(None, description="元数据(文本)")


class CVProcessRequest(BaseModel):
    """OpenCV 图片处理请求"""
    file_ids: List[int] = Field(..., description="文件ID列表（支持批量）")
    operation: str = Field(..., description="操作类型")
    params: dict = Field(default_factory=dict, description="操作参数")


class AIProcessRequest(BaseModel):
    """AI 图片处理请求"""
    file_ids: List[int] = Field(..., description="文件ID列表（支持批量）")
    ai_proxy_id: int = Field(..., description="AI代理ID")
    prompt: Optional[str] = Field(None, description="处理提示词（手动输入）")
    skill_id: Optional[int] = Field(None, description="Skill ID（从技能库选择）")


class OCRRequest(BaseModel):
    """OCR 文本提取请求"""
    file_ids: List[int] = Field(..., description="文件ID列表（支持批量）")
    workspace_id: int = Field(..., description="工作区ID（提取后保存到文档数据）")


class ImportRoadMaterialRequest(BaseModel):
    """从路网素材导入请求"""
    workspace_id: int = Field(..., description="工作区ID")
    material_ids: List[int] = Field(..., description="路网素材ID列表")
    source_type: str = Field("original", description="导入目标层级: original / ai_analysis")


class BatchDeleteRequest(BaseModel):
    """批量删除请求"""
    file_ids: List[int] = Field(..., description="文件ID列表")


class CopyRecordsRequest(BaseModel):
    """复制文件记录到另一工作区（不拷贝物理文件）"""
    file_ids: List[int] = Field(..., description="文件ID列表")
    target_workspace_id: int = Field(..., description="目标工作区ID")


class SetBaseUrlRequest(BaseModel):
    """设置静态文件 BaseUrl"""
    base_url: str = Field("", description="公网访问基础地址，如 http://example.com:9999")


class ImportExtractedImagesRequest(BaseModel):
    """导入从文档提取的图片到静态文件区"""
    workspace_id: int = Field(..., description="工作区ID")
    source_type: str = Field("original", description="导入目标层级: original / ai_analysis")
    temp_paths: List[str] = Field(..., description="提取图片的临时文件路径列表")
    file_names: List[str] = Field(default_factory=list, description="可选：与 temp_paths 一一对应的文件名")
    source_doc_name: str = Field("", description="来源文档名称（用于记录来源）")


# 支持的 OpenCV 操作及参数说明
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
