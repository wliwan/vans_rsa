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


class CopyToWorkspaceRequest(BaseModel):
    target_workspace_id: int = Field(..., description="目标工作区ID")
    sheet_ids: Optional[List[int]] = Field(default_factory=list, description="要复制的表格ID")
    analysis_ids: Optional[List[int]] = Field(default_factory=list, description="要复制的分析ID")
    document_ids: Optional[List[int]] = Field(default_factory=list, description="要复制的文档ID")
    static_file_ids: Optional[List[int]] = Field(default_factory=list, description="要复制的静态文件ID")


# ── 数据库导入 Schema ──

class MySQLConnectRequest(BaseModel):
    host: str = Field(..., description="主机地址", example="127.0.0.1")
    port: int = Field(3306, description="端口", example=3306)
    user: str = Field(..., description="用户名", example="root")
    password: str = Field("", description="密码")
    database: str = Field(..., description="数据库名", example="test_db")


class MySQLImportRequest(BaseModel):
    workspace_id: int = Field(..., description="工作区ID")
    host: str = Field(..., description="主机地址")
    port: int = Field(3306, description="端口")
    user: str = Field(..., description="用户名")
    password: str = Field("", description="密码")
    database: str = Field(..., description="数据库名")
    tables: List[str] = Field(..., description="要导入的表名列表", min_length=1)


class SQLiteImportRequest(BaseModel):
    workspace_id: int = Field(..., description="工作区ID")
    file_path: str = Field(..., description="已上传的 SQLite 文件路径")
    tables: List[str] = Field(..., description="要导入的表名列表", min_length=1)


class PixelImportRequest(BaseModel):
    workspace_id: int = Field(..., description="工作区ID")
    pixel_account_id: int = Field(..., description="像素账户ID")
    table_name: str = Field(..., description="数据表名")
    table_label: str = Field("", description="数据表显示名称")


class RoadNetworkImportRequest(BaseModel):
    workspace_id: int = Field(..., description="工作区ID")
    region_id: int = Field(..., description="区域ID")
    road_network_ids: List[int] = Field(..., description="要导入统计的路网文件ID列表", min_length=1)
