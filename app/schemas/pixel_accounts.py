from pydantic import BaseModel, Field
from typing import List, Optional


class PixelAccountCreate(BaseModel):
    username: str = Field(..., description="像素平台用户名", example="pixel_user")
    password: str = Field(..., description="像素平台密码", example="password123")
    tenant_address: str = Field(..., description="租户地址(org)", example="Qator")
    user_ids: Optional[List[int]] = Field(default=[], description="可访问的VFA用户ID列表")


class PixelAccountUpdate(BaseModel):
    id: int
    username: str = Field(..., description="像素平台用户名")
    password: str = Field(..., description="像素平台密码")
    tenant_address: str = Field(..., description="租户地址(org)")
    user_ids: Optional[List[int]] = Field(default=[], description="可访问的VFA用户ID列表")
