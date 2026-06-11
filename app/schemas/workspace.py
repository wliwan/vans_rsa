from typing import List, Optional

from pydantic import BaseModel, Field


class WorkspaceCreate(BaseModel):
    name: str = Field(..., description="工作区名称", example="销售数据分析")
    description: str = Field("", description="描述")
    user_ids: Optional[List[int]] = Field(default_factory=list, description="可访问用户ID")

    def create_dict(self):
        return self.model_dump(exclude_unset=True, exclude={"user_ids"})


class WorkspaceUpdate(BaseModel):
    id: int
    name: str = Field(..., description="工作区名称")
    description: str = Field("", description="描述")
    user_ids: Optional[List[int]] = Field(default_factory=list, description="可访问用户ID")


class AnalysisRequest(BaseModel):
    workspace_id: int = Field(..., description="工作区ID")
    sheet_id: int = Field(..., description="原始表格ID")
    ai_proxy_id: int = Field(..., description="AI代理ID")
    skill_id: Optional[int] = Field(None, description="Skill ID（可选）")
    prompt: Optional[str] = Field("", description="额外分析提示词")
    name: str = Field(..., description="分析名称")


class CorrelationRequest(BaseModel):
    workspace_id: int = Field(..., description="工作区ID")
    sheet_a_id: int = Field(..., description="表格A ID")
    sheet_b_id: int = Field(..., description="表格B ID")
    ai_proxy_id: int = Field(..., description="AI代理ID")
    skill_id: Optional[int] = Field(None, description="Skill ID（可选）")
    prompt: Optional[str] = Field("", description="额外分析提示词")
    name: str = Field(..., description="分析名称")


class BatchDeleteRequest(BaseModel):
    analysis_ids: List[int] = Field(..., description="分析表格ID列表")
