"""国际化管理 Schema"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class LocaleField(BaseModel):
    """单个 locale 下的翻译字段"""
    key: str = Field(..., description="字段路径，如 header.label_profile")
    value: Any = Field(..., description="翻译值（字符串或嵌套对象）")
    type: str = Field("string", description="值类型: string / object / array")


class I18nEntry(BaseModel):
    """国际化条目（一行，跨所有语言的同一个 key）"""
    key: str = Field(..., description="字段路径，如 header.label_profile")
    type: str = Field("string", description="类型: string / object / array")
    translations: Dict[str, Any] = Field(
        default_factory=dict,
        description="各语言的翻译值，如 {'cn': '个人信息', 'en': 'Profile'}",
    )


class I18nListResponse(BaseModel):
    """国际化列表响应"""
    locales: List[str] = Field(..., description="可用语言列表，如 ['cn', 'en', 'tr']")
    entries: List[I18nEntry] = Field(..., description="国际化条目列表")


class I18nUpdateRequest(BaseModel):
    """更新单条翻译"""
    key: str = Field(..., description="字段路径")
    locale: str = Field(..., description="语言代码，如 cn/en/tr")
    value: Any = Field(..., description="新的翻译值")


class I18nBatchUpdateRequest(BaseModel):
    """批量更新翻译"""
    updates: List[I18nUpdateRequest] = Field(..., description="批量更新列表")


class I18nImportRequest(BaseModel):
    """导入国际化数据"""
    locale: str = Field(..., description="目标语言代码，如 jp/fr")
    data: Dict[str, Any] = Field(..., description="完整翻译 JSON，key 为字段路径")


class I18nAIGenerateRequest(BaseModel):
    """AI 翻译请求"""
    ai_proxy_name: str = Field(..., description="AI 代理名称")
    target_locale: str = Field(..., description="目标语言代码，如 en/jp/fr/de")
    mode: str = Field("full", description="翻译模式: full=全量替换, incremental=增量补充（只翻译缺失条目）")


class ProcessScanRequest(BaseModel):
    """接收前端 AST 扫描结果，AI 生成 key 并追加到 cn.json"""
    ai_proxy_name: str = Field(..., description="AI 代理名称")
    items: List[dict] = Field(..., description="扫描结果列表，每项含 {file, line, text}")


class I18nBatchDeleteRequest(BaseModel):
    """批量删除国际化字段"""
    keys: List[str] = Field(..., description="要删除的字段 key 列表")


class ScanNewFieldItem(BaseModel):
    """单条扫描结果（新字段）"""
    file: str = Field(..., description="文件相对路径，如 web/src/views/xxx/index.vue")
    line: int = Field(..., description="行号")
    text: str = Field(..., description="硬编码中文文本")
    context: str = Field("", description="所在行的上下文（截断到 200 字符）")
    prefix: str = Field("common", description="推导的 i18n key 前缀")
    source: str = Field(
        "unknown",
        description="检测来源: html-inline | html-attribute | js-string | template-interpolation",
    )


class ScanNewFieldsResponse(BaseModel):
    """扫描新字段响应"""
    total: int = Field(..., description="待翻译字段总数")
    items: List[ScanNewFieldItem] = Field(default_factory=list, description="字段详情列表")


class ProcessScanRequest(BaseModel):
    """接收扫描结果，AI 生成 key 并追加到 cn.json"""
    ai_proxy_name: str = Field(..., description="AI 代理名称")
    items: List[dict] = Field(..., description="扫描结果列表，每项含 {file, line, text}")
    safe_mode: bool = Field(
        True,
        description="安全模式 (默认 true): 只写 cn.json 不修改源 Vue 文件；false: 同时回写源文件",
    )