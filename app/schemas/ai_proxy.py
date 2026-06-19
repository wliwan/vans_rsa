from typing import List, Optional

from pydantic import BaseModel, Field


class AIProxyCreate(BaseModel):
    name: str = Field(..., description="代理名称", example="GPT-4")
    url: Optional[str] = Field(None, description="接口地址", example="https://api.openai.com/v1")
    token: Optional[str] = Field(None, description="认证令牌")
    model: Optional[str] = Field(None, description="模型名称", example="gpt-4")
    user_ids: Optional[List[int]] = Field(default_factory=list, description="可访问用户ID列表")

    def create_dict(self):
        return self.model_dump(exclude_unset=True, exclude={"user_ids"})


class AIProxyUpdate(BaseModel):
    name: str = Field(..., description="代理名称（定位用）")
    url: Optional[str] = Field(None, description="接口地址")
    token: Optional[str] = Field(None, description="认证令牌")
    model: Optional[str] = Field(None, description="模型名称")
    user_ids: Optional[List[int]] = Field(default_factory=list, description="可访问用户ID列表")
