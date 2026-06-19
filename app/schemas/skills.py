from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class SkillCreate(BaseModel):
    title: str = Field(..., description="标题", example="技能文档")
    content: str = Field("", description="Markdown内容")
    user_ids: Optional[List[int]] = Field(default_factory=list, description="可访问用户ID列表")

    def create_dict(self):
        return self.model_dump(exclude_unset=True, exclude={"user_ids"})


class SkillUpdate(BaseModel):
    id: int
    title: str = Field(..., description="标题")
    content: str = Field("", description="Markdown内容")
    user_ids: Optional[List[int]] = Field(default_factory=list, description="可访问用户ID列表")


class SkillAICreate(BaseModel):
    proxy_name: str = Field(..., description="AI代理名称", example="GPT-4")
    source_skill_id: Optional[int] = Field(None, description="参考技能ID（可选）")
    prompt: str = Field(..., description="用户提示词", example="生成一个关于数据分析的技能文档")
    user_ids: Optional[List[int]] = Field(default_factory=list, description="可访问用户ID列表")


class SkillUser(BaseModel):
    id: int
    username: str
    alias: Optional[str] = None
