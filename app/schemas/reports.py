from typing import List, Optional

from pydantic import BaseModel, Field


class ReportCreate(BaseModel):
    workspace_id: int = Field(..., description="工作区ID")
    name: str = Field(..., description="报告名称")
    source_sheet_ids: List[int] = Field(default_factory=list, description="原始表格ID列表")
    source_analysis_ids: List[int] = Field(default_factory=list, description="分析表格ID列表")
    source_document_ids: List[int] = Field(default_factory=list, description="文档ID列表")
    source_static_ids: List[int] = Field(default_factory=list, description="静态文件ID列表")
    ai_proxy_id: int = Field(..., description="AI代理ID")
    skill_id: Optional[int] = Field(None, description="Skill ID")
    prompt: str = Field("", description="生成提示词")


class ReportUpdate(BaseModel):
    id: int
    name: Optional[str] = Field(None, description="报告名称")
    content: Optional[str] = Field(None, description="HTML内容")


class ReportClone(BaseModel):
    id: int = Field(..., description="源报告ID")
    name: str = Field(..., description="新报告名称")


class ReportPreviewSources(BaseModel):
    sheet_ids: List[int] = Field(default_factory=list, description="表格ID列表")
    analysis_ids: List[int] = Field(default_factory=list, description="分析表格ID列表")
    document_ids: List[int] = Field(default_factory=list, description="文档ID列表")
    static_file_ids: List[int] = Field(default_factory=list, description="静态文件ID列表")


class SourcePreviewItem(BaseModel):
    id: int
    name: str
    type: str  # sheet / analysis / document / static_file
    preview: str  # MD 格式预览
    char_count: int = 0
    file_size: int = 0


class ReportPreviewResponse(BaseModel):
    md_preview: str = ""  # 拼接的完整 MD 预览
    items: List[SourcePreviewItem] = []
    total_chars: int = 0
    estimated_tokens: int = 0
    source_counts: dict = Field(default_factory=dict)  # {"sheets": 3, "documents": 5, ...}
