"""调研问卷 Schema"""
from typing import Any, List, Optional

from pydantic import BaseModel, Field


class SurveyCreate(BaseModel):
    """创建问卷（AI生成）"""
    name: str = Field(..., description="问卷模板名称", example="客户满意度调查")
    ai_proxy_id: int = Field(..., description="AI代理ID")
    skill_id: int = Field(..., description="技能ID")
    prompt: str = Field(..., description="生成提示词（示例数据）", example="请创建一个客户满意度调查网页，包含以下字段：姓名、电话、评分(1-5)、建议")
    user_ids: List[int] = Field(default_factory=list, description="授权用户ID列表")


class SurveyUpdate(BaseModel):
    """更新问卷"""
    id: int = Field(..., description="问卷ID")
    name: Optional[str] = Field(None, description="问卷名称")
    user_ids: Optional[List[int]] = Field(None, description="授权用户ID列表")


class SurveySubmissionCreate(BaseModel):
    """问卷提交（来自问卷网页）— v3.0 content 改为 JSON 文本"""
    survey_token: str = Field(..., description="问卷短链接令牌")
    submitter_name: Optional[str] = Field(None, description="提交者姓名")
    submitter_info: Optional[dict] = Field(None, description="提交者信息")
    content: str = Field(..., description="提交内容(JSON文本)")
    word_count: Optional[int] = Field(0, description="内容字数")
    raw_data: Optional[dict] = Field(None, description="原始表单数据(扁平JSON)")
    save_type: str = Field("submit", description="保存类型: save(本地草稿) / submit(提交)")


class SurveySubmissionOut(BaseModel):
    """问卷提交记录输出 — v3.0 content 为 JSON 文本"""
    id: int
    survey_id: int
    submitter_name: Optional[str] = None
    submitter_info: Optional[dict] = None
    content: str  # JSON 文本
    word_count: int
    raw_data: Optional[dict] = None
    save_type: str
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
