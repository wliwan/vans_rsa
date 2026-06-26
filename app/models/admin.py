from tortoise import fields

from app.schemas.menus import MenuType

from .base import BaseModel, TimestampMixin
from .enums import (
    BoundaryStatus, BoundaryType, MethodType, RegionType,
    RoadNetworkStatus, RoadNetworkType,
)


class User(BaseModel, TimestampMixin):
    username = fields.CharField(max_length=20, unique=True, description="用户名称", index=True)
    alias = fields.CharField(max_length=30, null=True, description="姓名", index=True)
    email = fields.CharField(max_length=255, unique=True, description="邮箱", index=True)
    phone = fields.CharField(max_length=20, null=True, description="电话", index=True)
    password = fields.CharField(max_length=128, null=True, description="密码")
    is_active = fields.BooleanField(default=True, description="是否激活", index=True)
    is_superuser = fields.BooleanField(default=False, description="是否为超级管理员", index=True)
    last_login = fields.DatetimeField(null=True, description="最后登录时间", index=True)
    roles = fields.ManyToManyField("models.Role", related_name="user_roles")
    dept_id = fields.IntField(null=True, description="部门ID", index=True)

    class Meta:
        table = "user"


class Role(BaseModel, TimestampMixin):
    name = fields.CharField(max_length=20, unique=True, description="角色名称", index=True)
    desc = fields.CharField(max_length=500, null=True, description="角色描述")
    menus = fields.ManyToManyField("models.Menu", related_name="role_menus")
    apis = fields.ManyToManyField("models.Api", related_name="role_apis")

    class Meta:
        table = "role"


class Api(BaseModel, TimestampMixin):
    path = fields.CharField(max_length=100, description="API路径", index=True)
    method = fields.CharEnumField(MethodType, description="请求方法", index=True)
    summary = fields.CharField(max_length=500, description="请求简介", index=True)
    tags = fields.CharField(max_length=100, description="API标签", index=True)

    class Meta:
        table = "api"


class Menu(BaseModel, TimestampMixin):
    name = fields.CharField(max_length=20, description="菜单名称", index=True)
    remark = fields.JSONField(null=True, description="保留字段")
    menu_type = fields.CharEnumField(MenuType, null=True, description="菜单类型")
    icon = fields.CharField(max_length=100, null=True, description="菜单图标")
    path = fields.CharField(max_length=100, description="菜单路径", index=True)
    order = fields.IntField(default=0, description="排序", index=True)
    parent_id = fields.IntField(default=0, description="父菜单ID", index=True)
    is_hidden = fields.BooleanField(default=False, description="是否隐藏")
    component = fields.CharField(max_length=100, description="组件")
    keepalive = fields.BooleanField(default=True, description="存活")
    redirect = fields.CharField(max_length=100, null=True, description="重定向")

    class Meta:
        table = "menu"


class Dept(BaseModel, TimestampMixin):
    name = fields.CharField(max_length=20, unique=True, description="部门名称", index=True)
    desc = fields.CharField(max_length=500, null=True, description="备注")
    is_deleted = fields.BooleanField(default=False, description="软删除标记", index=True)
    order = fields.IntField(default=0, description="排序", index=True)
    parent_id = fields.IntField(default=0, max_length=10, description="父部门ID", index=True)

    class Meta:
        table = "dept"


class DeptClosure(BaseModel, TimestampMixin):
    ancestor = fields.IntField(description="父代", index=True)
    descendant = fields.IntField(description="子代", index=True)
    level = fields.IntField(default=0, description="深度", index=True)


class AuditLog(BaseModel, TimestampMixin):
    user_id = fields.IntField(description="用户ID", index=True)
    username = fields.CharField(max_length=64, default="", description="用户名称", index=True)
    module = fields.CharField(max_length=64, default="", description="功能模块", index=True)
    summary = fields.CharField(max_length=128, default="", description="请求描述", index=True)
    method = fields.CharField(max_length=10, default="", description="请求方法", index=True)
    path = fields.CharField(max_length=255, default="", description="请求路径", index=True)
    status = fields.IntField(default=-1, description="状态码", index=True)
    response_time = fields.IntField(default=0, description="响应时间(单位ms)", index=True)
    request_args = fields.JSONField(null=True, description="请求参数")
    response_body = fields.JSONField(null=True, description="返回数据")


class PixelAccount(BaseModel, TimestampMixin):
    username = fields.CharField(max_length=100, description="像素平台用户名", index=True)
    password = fields.CharField(max_length=256, description="像素平台密码")
    tenant_address = fields.CharField(max_length=200, description="租户地址(org)", index=True)
    country = fields.CharField(max_length=100, null=True, description="国家")
    state = fields.CharField(max_length=100, null=True, description="区域")
    base_url = fields.CharField(max_length=300, null=True, description="平台基础URL")
    renter = fields.CharField(max_length=100, null=True, description="租户标识")
    users = fields.ManyToManyField("models.User", related_name="pixel_accounts")

    class Meta:
        table = "pixel_account"


class Defect(BaseModel, TimestampMixin):
    remote_id = fields.CharField(max_length=64, description="远程ID", index=True)
    pixel_account = fields.ForeignKeyField("models.PixelAccount", related_name="defects", description="像素平台账户", index=True)
    longitude = fields.FloatField(null=True, description="经度")
    latitude = fields.FloatField(null=True, description="纬度")
    longitude_gc = fields.FloatField(null=True, description="GCJ02经度")
    latitude_gc = fields.FloatField(null=True, description="GCJ02纬度")
    track_image = fields.CharField(max_length=500, null=True, description="轨迹图像URL")
    track_url = fields.CharField(max_length=500, null=True, description="轨迹URL")
    status = fields.IntField(null=True, description="状态码", index=True)
    status_name = fields.CharField(max_length=100, null=True, description="状态名称")
    risk_type = fields.CharField(max_length=64, null=True, description="风险类型ID")
    risk_level = fields.IntField(null=True, description="风险等级", index=True)
    risk_level_name = fields.CharField(max_length=50, null=True, description="风险等级名称")
    risk_name1 = fields.CharField(max_length=100, null=True, description="风险一级分类")
    risk_name2 = fields.CharField(max_length=100, null=True, description="风险二级分类")
    risk_name3 = fields.CharField(max_length=100, null=True, description="风险三级分类")
    risk_time = fields.DatetimeField(null=True, description="风险时间", index=True)
    city_code = fields.CharField(max_length=20, null=True, description="城市代码")
    city_name = fields.CharField(max_length=100, null=True, description="城市名称")
    org_code = fields.CharField(max_length=100, null=True, description="组织代码")
    road_name = fields.CharField(max_length=200, null=True, description="道路名称", index=True)
    data_from = fields.IntField(null=True, description="数据来源")
    data_from_name = fields.CharField(max_length=100, null=True, description="数据来源名称")
    region_name = fields.CharField(max_length=100, null=True, description="区域名称")
    town_name = fields.CharField(max_length=100, null=True, description="城镇名称")
    subd_name = fields.CharField(max_length=100, null=True, description="子区域名称")
    reverse_name = fields.CharField(max_length=50, null=True, description="方向")
    car_no = fields.CharField(max_length=50, null=True, description="车牌号")
    lane = fields.CharField(max_length=20, null=True, description="车道")
    extra_data = fields.JSONField(null=True, description="扩展数据")

    class Meta:
        table = "defect"


class Track(BaseModel, TimestampMixin):
    remote_id = fields.CharField(max_length=64, description="远程ID", index=True)
    pixel_account = fields.ForeignKeyField("models.PixelAccount", related_name="tracks", description="像素平台账户", index=True)
    car_id = fields.CharField(max_length=64, description="车辆ID", index=True)
    road_name = fields.CharField(max_length=200, null=True, description="道路名称", index=True)
    car_type = fields.IntField(null=True, description="车辆类型")
    longitude = fields.CharField(max_length=30, null=True, description="经度")
    latitude = fields.CharField(max_length=30, null=True, description="纬度")
    flag = fields.IntField(null=True, description="标志")
    track_time = fields.DatetimeField(null=True, description="轨迹时间", index=True)
    extra_data = fields.JSONField(null=True, description="扩展数据")

    class Meta:
        table = "track"


class Region(BaseModel, TimestampMixin):
    name = fields.CharField(max_length=200, description="名称", index=True)
    local_name = fields.CharField(max_length=200, null=True, description="本地名称")
    code = fields.CharField(max_length=20, null=True, description="ISO代码", index=True)
    iso_alpha2 = fields.CharField(max_length=2, null=True, description="ISO Alpha-2")
    iso_alpha3 = fields.CharField(max_length=3, null=True, description="ISO Alpha-3")
    iso_numeric = fields.CharField(max_length=3, null=True, description="ISO Numeric")
    region_type = fields.CharEnumField(RegionType, description="类型", index=True)
    parent = fields.ForeignKeyField("models.Region", null=True, related_name="children", description="父级", index=True)
    capital = fields.CharField(max_length=200, null=True, description="首都/首府")
    population = fields.BigIntField(null=True, description="人口")
    area = fields.FloatField(null=True, description="面积(km²)")
    latitude = fields.FloatField(null=True, description="纬度")
    longitude = fields.FloatField(null=True, description="经度")
    timezone = fields.CharField(max_length=100, null=True, description="时区")
    is_active = fields.BooleanField(default=True, description="是否启用", index=True)

    class Meta:
        table = "region"


class RegionBoundary(BaseModel, TimestampMixin):
    region = fields.ForeignKeyField("models.Region", related_name="boundaries", description="区域", index=True)
    file_name = fields.CharField(max_length=200, description="文件名")
    file_type = fields.CharEnumField(BoundaryType, default=BoundaryType.GEOJSON, description="文件类型")
    file_path = fields.CharField(max_length=500, description="存储路径")
    file_size = fields.BigIntField(null=True, description="文件大小(字节)")
    srid = fields.CharField(max_length=20, null=True, default="EPSG:4326", description="坐标系")
    download_status = fields.CharEnumField(BoundaryStatus, default=BoundaryStatus.PENDING, description="下载状态", index=True)
    error_message = fields.CharField(max_length=500, null=True, description="错误信息")
    is_active = fields.BooleanField(default=True, description="是否启用")

    class Meta:
        table = "region_boundary"


class RoadNetwork(BaseModel, TimestampMixin):
    region = fields.ForeignKeyField("models.Region", related_name="road_networks", description="区域", index=True)
    file_name = fields.CharField(max_length=200, description="文件名")
    file_type = fields.CharEnumField(RoadNetworkType, default=RoadNetworkType.GRAPHML, description="文件类型")
    file_path = fields.CharField(max_length=500, description="存储路径")
    file_size = fields.BigIntField(null=True, description="文件大小(字节)")
    node_count = fields.BigIntField(null=True, description="节点数")
    edge_count = fields.BigIntField(null=True, description="边数")
    srid = fields.CharField(max_length=20, null=True, default="EPSG:4326", description="坐标系")
    download_mode = fields.CharField(max_length=50, null=True, description="下载模式: boundary / name")
    download_status = fields.CharEnumField(RoadNetworkStatus, default=RoadNetworkStatus.PENDING, description="下载状态", index=True)
    error_message = fields.CharField(max_length=500, null=True, description="错误信息")
    stats_json = fields.TextField(null=True, description="分析统计缓存(JSON): info + highway_types + bbox")
    is_active = fields.BooleanField(default=True, description="是否启用")

    class Meta:
        table = "road_network"


class Skill(BaseModel, TimestampMixin):
    title = fields.CharField(max_length=200, description="标题", index=True)
    content = fields.TextField(description="Markdown内容")
    users = fields.ManyToManyField("models.User", related_name="skills", description="可访问的用户")

    class Meta:
        table = "skill"


class AIProxy(BaseModel, TimestampMixin):
    name = fields.CharField(max_length=100, unique=True, description="代理名称", index=True)
    url = fields.CharField(max_length=500, null=True, description="接口地址")
    token = fields.CharField(max_length=500, null=True, description="认证令牌")
    model = fields.CharField(max_length=200, null=True, description="模型名称")
    users = fields.ManyToManyField("models.User", related_name="ai_proxies", description="可访问的用户")

    class Meta:
        table = "ai_proxy"


class Workspace(BaseModel, TimestampMixin):
    name = fields.CharField(max_length=200, description="工作区名称", index=True)
    description = fields.CharField(max_length=500, null=True, description="描述")
    users = fields.ManyToManyField("models.User", related_name="workspaces", description="可访问的用户")

    class Meta:
        table = "workspace"


class OriginalSheet(BaseModel, TimestampMixin):
    workspace = fields.ForeignKeyField("models.Workspace", related_name="original_sheets", description="所属工作区", index=True)
    name = fields.CharField(max_length=200, description="文件名", index=True)
    file_path = fields.CharField(max_length=500, description="存储路径")
    file_size = fields.BigIntField(default=0, description="文件大小(字节)")

    class Meta:
        table = "original_sheet"


class AnalysisSheet(BaseModel, TimestampMixin):
    workspace = fields.ForeignKeyField("models.Workspace", related_name="analysis_sheets", description="所属工作区", index=True)
    name = fields.CharField(max_length=200, description="分析名称", index=True)
    file_path = fields.CharField(max_length=500, description="存储路径")
    file_size = fields.BigIntField(default=0, description="文件大小(字节)")
    source_type = fields.CharField(max_length=20, description="来源类型: analysis / correlation")
    source_sheet = fields.ForeignKeyField("models.OriginalSheet", null=True, related_name="analysis_results", description="来源原始表格", index=True)
    related_sheet = fields.ForeignKeyField("models.OriginalSheet", null=True, related_name="correlation_results", description="关联分析的关联表格", index=True)
    ai_proxy_id = fields.IntField(null=True, description="使用的AI代理ID")
    skill_id = fields.IntField(null=True, description="使用的Skill ID")
    prompt = fields.TextField(null=True, description="分析提示词")

    class Meta:
        table = "analysis_sheet"


class Document(BaseModel, TimestampMixin):
    workspace = fields.ForeignKeyField("models.Workspace", related_name="documents", description="所属工作区", index=True)
    name = fields.CharField(max_length=200, description="文件名", index=True)
    file_path = fields.CharField(max_length=500, description="存储路径")
    file_size = fields.BigIntField(default=0, description="文件大小(字节)")
    char_count = fields.IntField(default=0, description="字符数量")
    source_type = fields.CharField(max_length=20, description="来源类型: original / analysis")
    source_document = fields.ForeignKeyField("models.Document", null=True, related_name="analysis_documents", description="来源原始文档", index=True)
    import_source = fields.CharField(max_length=20, null=True, description="数据库导入来源: mysql / sqlite / pixel / road_network")
    source_table = fields.CharField(max_length=200, null=True, description="原始数据库表名")
    row_count = fields.IntField(null=True, description="数据行数")
    dump_date = fields.DatetimeField(null=True, description="数据导出时间")
    source_last_updated = fields.DatetimeField(null=True, description="源数据最后更新时间")
    ai_proxy_id = fields.IntField(null=True, description="使用的AI代理ID")
    skill_id = fields.IntField(null=True, description="使用的Skill ID")
    prompt = fields.TextField(null=True, description="分析提示词")

    class Meta:
        table = "document"


class Report(BaseModel, TimestampMixin):
    workspace = fields.ForeignKeyField("models.Workspace", related_name="reports", description="所属工作区", index=True)
    name = fields.CharField(max_length=200, description="报告名称", index=True)
    content = fields.TextField(description="HTML内容")
    source_sheet_ids = fields.JSONField(default=list, description="引用的原始表格ID列表")
    source_analysis_ids = fields.JSONField(default=list, description="引用的分析表格ID列表")
    source_document_ids = fields.JSONField(default=list, description="引用的文档ID列表")
    source_static_ids = fields.JSONField(default=list, description="引用的静态文件ID列表")
    ai_proxy_id = fields.IntField(null=True, description="使用的AI代理ID")
    skill_id = fields.IntField(null=True, description="使用的Skill ID")
    prompt = fields.TextField(null=True, description="生成提示词")
    system_prompt = fields.TextField(null=True, description="系统提示词")

    class Meta:
        table = "report"


class SystemConfig(BaseModel, TimestampMixin):
    key = fields.CharField(max_length=100, unique=True, description="配置键", index=True)
    value = fields.TextField(description="配置值(JSON)")
    description = fields.CharField(max_length=200, null=True, description="配置说明")

    class Meta:
        table = "system_config"


class FilterTemplate(BaseModel, TimestampMixin):
    name = fields.CharField(max_length=50, unique=True, description="模板名称", index=True)
    selected_types = fields.JSONField(default=list, description="选中的道路等级列表")
    is_preset = fields.BooleanField(default=False, description="是否系统预设模板")

    class Meta:
        table = "filter_template"


class RoadMaterial(BaseModel, TimestampMixin):
    """路网素材 - 图片素材管理"""
    name = fields.CharField(max_length=200, description="图片名称", index=True)
    description = fields.TextField(null=True, description="元数据(文本)")
    region = fields.ForeignKeyField("models.Region", related_name="materials", description="所属区域", index=True)
    file_name = fields.CharField(max_length=300, description="原始文件名")
    file_path = fields.CharField(max_length=500, description="存储路径")
    file_size = fields.BigIntField(default=0, description="文件大小(字节)")
    width = fields.IntField(null=True, description="图片宽度(px)")
    height = fields.IntField(null=True, description="图片高度(px)")
    color_mode = fields.CharField(max_length=20, null=True, description="色彩模式(RGB/RGBA/CMYK等)")
    bit_depth = fields.IntField(null=True, description="位深度")
    dpi = fields.FloatField(null=True, description="DPI/PPI")
    format_type = fields.CharField(max_length=10, null=True, description="格式类型(JPEG/PNG/TIFF等)")
    exif_data = fields.JSONField(null=True, description="EXIF元数据")
    source = fields.CharField(max_length=50, default="upload", description="图片来源(upload/import/ai_generated/cv_processed)")
    short_url_token = fields.CharField(max_length=64, unique=True, description="短链接令牌", index=True)

    class Meta:
        table = "road_material"


class Survey(BaseModel, TimestampMixin):
    """调研问卷 — 调研中心问卷工作台"""
    name = fields.CharField(max_length=200, description="问卷名称", index=True)
    file_name = fields.CharField(max_length=300, description="原始文件名")
    file_path = fields.CharField(max_length=500, description="网页文件存储路径")
    file_size = fields.BigIntField(default=0, description="文件大小(字节)")
    ai_proxy_id = fields.IntField(null=True, description="使用的AI代理ID", index=True)
    skill_id = fields.IntField(null=True, description="使用的Skill ID", index=True)
    prompt = fields.TextField(null=True, description="生成提示词")
    short_url_token = fields.CharField(max_length=64, unique=True, null=True, description="短链接令牌", index=True)
    is_valid = fields.BooleanField(default=True, description="安全审核是否通过", index=True)
    security_log = fields.TextField(null=True, description="安全审核日志")
    creator_id = fields.IntField(null=True, description="创建者ID", index=True)
    users = fields.ManyToManyField("models.User", related_name="surveys", description="授权访问的用户")

    class Meta:
        table = "survey"


class SurveySubmission(BaseModel, TimestampMixin):
    """问卷提交记录 — 用户通过问卷网页提交的数据"""
    survey = fields.ForeignKeyField("models.Survey", related_name="submissions", description="所属问卷", index=True)
    submitter_name = fields.CharField(max_length=100, null=True, description="提交者姓名")
    submitter_info = fields.JSONField(null=True, description="提交者信息(JSON)")
    content = fields.TextField(description="提交内容(Markdown表格)")
    word_count = fields.IntField(default=0, description="内容总字数")
    raw_data = fields.JSONField(null=True, description="原始表单数据(JSON)")
    save_type = fields.CharField(max_length=20, default="submit", description="保存类型: save(本地) / submit(提交)", index=True)

    class Meta:
        table = "survey_submission"


class StaticFile(BaseModel, TimestampMixin):
    """静态文件数据 — 工作台静态文件TAB的两级目录管理"""
    workspace = fields.ForeignKeyField("models.Workspace", related_name="static_files", description="所属工作区", index=True)
    name = fields.CharField(max_length=200, description="文件名称（用户可编辑）", index=True)
    description = fields.TextField(null=True, description="元数据（文本，用户可输入）")
    file_name = fields.CharField(max_length=300, description="原始文件名")
    file_path = fields.CharField(max_length=500, description="存储路径")
    file_size = fields.BigIntField(default=0, description="文件大小(字节)")
    source_type = fields.CharField(max_length=20, default="original", description="目录层级: original / ai_analysis", index=True)
    is_image = fields.BooleanField(default=False, description="是否为图片文件")
    width = fields.IntField(null=True, description="图片宽度(px)")
    height = fields.IntField(null=True, description="图片高度(px)")
    color_mode = fields.CharField(max_length=20, null=True, description="色彩模式(RGB/RGBA/CMYK等)")
    bit_depth = fields.IntField(null=True, description="位深度")
    dpi = fields.FloatField(null=True, description="DPI/PPI")
    format_type = fields.CharField(max_length=10, null=True, description="格式类型(JPEG/PNG/TIFF等)")
    exif_data = fields.JSONField(null=True, description="EXIF元数据")
    source = fields.CharField(max_length=50, default="upload", description="来源: upload / cv_processed / ai_generated / ocr / road_material / auto")
    parent_file = fields.ForeignKeyField("models.StaticFile", null=True, related_name="children", description="父文件（AI处理后关联原始文件）", index=True)
    short_url_token = fields.CharField(max_length=64, unique=True, null=True, description="短链接令牌", index=True)

    class Meta:
        table = "static_file"


