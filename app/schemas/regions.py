"""全球国家及行政区 Schema"""
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field

from app.models.enums import (
    BoundaryStatus, BoundaryType, RegionType,
    RoadNetworkStatus, RoadNetworkType,
)


class RegionCreate(BaseModel):
    name: str = Field(..., description="名称")
    local_name: Optional[str] = Field(None, description="本地名称")
    code: Optional[str] = Field(None, description="ISO代码")
    iso_alpha2: Optional[str] = Field(None, max_length=2, description="ISO Alpha-2")
    iso_alpha3: Optional[str] = Field(None, max_length=3, description="ISO Alpha-3")
    iso_numeric: Optional[str] = Field(None, max_length=3, description="ISO Numeric")
    region_type: RegionType = Field(..., description="类型")
    parent_id: Optional[int] = Field(None, description="父级ID")
    capital: Optional[str] = Field(None, description="首都/首府")
    population: Optional[int] = Field(None, description="人口")
    area: Optional[float] = Field(None, description="面积(km²)")
    latitude: Optional[float] = Field(None, description="纬度")
    longitude: Optional[float] = Field(None, description="经度")
    timezone: Optional[str] = Field(None, description="时区")


class RegionUpdate(BaseModel):
    id: int
    name: Optional[str] = Field(None, description="名称")
    local_name: Optional[str] = Field(None, description="本地名称")
    code: Optional[str] = Field(None, description="ISO代码")
    iso_alpha2: Optional[str] = Field(None, max_length=2, description="ISO Alpha-2")
    iso_alpha3: Optional[str] = Field(None, max_length=3, description="ISO Alpha-3")
    iso_numeric: Optional[str] = Field(None, max_length=3, description="ISO Numeric")
    region_type: Optional[RegionType] = Field(None, description="类型")
    parent_id: Optional[int] = Field(None, description="父级ID")
    capital: Optional[str] = Field(None, description="首都/首府")
    population: Optional[int] = Field(None, description="人口")
    area: Optional[float] = Field(None, description="面积(km²)")
    latitude: Optional[float] = Field(None, description="纬度")
    longitude: Optional[float] = Field(None, description="经度")
    timezone: Optional[str] = Field(None, description="时区")
    is_active: Optional[bool] = Field(None, description="是否启用")


class RegionImportRequest(BaseModel):
    """批量导入 ISO 3166 国家数据"""
    pass


class ExportLevel(str, Enum):
    ALL = "ALL"
    STATE = "STATE"
    CITY = "CITY"


class RegionExportRequest(BaseModel):
    """导出请求"""
    country_id: int = Field(..., description="国家ID")
    level: ExportLevel = Field(ExportLevel.STATE, description="导出级别")


class RegionBatchUpdate(BaseModel):
    """批量更新"""
    updates: List[RegionUpdate] = Field(..., description="更新列表")


# ── Boundary Schemas ──

class BoundaryDownloadRequest(BaseModel):
    """从在线服务下载边界文件"""
    region_id: int = Field(..., description="区域ID")
    file_type: BoundaryType = Field(BoundaryType.GEOJSON, description="文件类型")


class BoundaryUploadRequest(BaseModel):
    """上传边界文件"""
    region_id: int = Field(..., description="区域ID")


class BoundaryOut(BaseModel):
    """边界文件输出"""
    id: int
    region_id: int
    file_name: str
    file_type: BoundaryType
    file_size: Optional[int] = None
    srid: Optional[str] = None
    download_status: BoundaryStatus
    error_message: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


# ── RoadNetwork Schemas ──

class RoadNetworkDownloadRequest(BaseModel):
    """路网下载请求"""
    region_id: int = Field(..., description="区域ID")
    mode: str = Field("boundary", description="下载模式: boundary(边界文件) / name(地名)")
    file_type: RoadNetworkType = Field(RoadNetworkType.GRAPHML, description="文件类型")


class RoadNetworkOut(BaseModel):
    """路网文件输出"""
    id: int
    region_id: int
    file_name: str
    file_type: RoadNetworkType
    file_size: Optional[int] = None
    node_count: Optional[int] = None
    edge_count: Optional[int] = None
    srid: Optional[str] = None
    download_mode: Optional[str] = None
    download_status: RoadNetworkStatus
    error_message: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
