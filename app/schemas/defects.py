"""病害数据 Schema — 同步、清除、查询"""
from datetime import date

from pydantic import BaseModel, Field


class DefectSyncRequest(BaseModel):
    """同步病害数据请求"""
    account_id: int = Field(..., description="像素平台账户ID")
    start_time: date = Field(..., description="开始日期")
    end_time: date = Field(..., description="结束日期")


class DefectClearRequest(BaseModel):
    """清除病害数据请求"""
    account_id: int = Field(..., description="像素平台账户ID")
