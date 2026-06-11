from typing import List, Optional

from pydantic import BaseModel, Field


class ReportCreate(BaseModel):
    workspace_id: int = Field(..., description="工作区ID")
    name: str = Field(..., description="报告名称")
    source_sheet_ids: List[int] = Field(default_factory=list, description="原始表格ID列表")
    source_analysis_ids: List[int] = Field(default_factory=list, description="分析表格ID列表")
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
