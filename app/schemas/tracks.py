"""轨迹点数据 Schema — 同步、清除"""
from datetime import date

from pydantic import BaseModel, Field


class TrackSyncRequest(BaseModel):
    """同步轨迹点数据请求"""
    account_id: int = Field(..., description="像素平台账户ID")
    car_id: str = Field(..., description="车辆ID")
    start_time: date = Field(..., description="开始日期")
    end_time: date = Field(..., description="结束日期")


class TrackClearRequest(BaseModel):
    """清除轨迹点数据请求"""
    account_id: int = Field(..., description="像素平台账户ID")
    car_id: str = Field("", description="车辆ID（为空则清除该账户所有轨迹）")
