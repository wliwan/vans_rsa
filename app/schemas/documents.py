from typing import List, Optional

from pydantic import BaseModel, Field


class DocumentAIAnalyze(BaseModel):
    workspace_id: int = Field(..., description="工作区ID")
    document_ids: List[int] = Field(..., description="原始文档ID列表")
    ai_proxy_id: int = Field(..., description="AI代理ID")
    skill_id: Optional[int] = Field(None, description="辅助Skill ID")
    prompt: Optional[str] = Field("", description="额外提示词")


class DocumentBatchDelete(BaseModel):
    document_ids: List[int] = Field(..., description="要删除的文档ID列表")


class DocumentCreateText(BaseModel):
    workspace_id: int = Field(..., description="工作区ID")
    name: str = Field(..., description="文档名称")
    content: str = Field(..., description="文档文本内容")


class DocumentUpdateContent(BaseModel):
    document_id: int = Field(..., description="文档ID")
    content: str = Field(..., description="文档内容(Markdown)")
    name: Optional[str] = Field(None, description="文档名称（可选，不传则不更新）")


class DocumentBatchExport(BaseModel):
    document_ids: List[int] = Field(..., description="要导出的文档ID列表")


class DocumentImportFromSurvey(BaseModel):
    workspace_id: int = Field(..., description="目标工作区ID")
    submission_id: int = Field(..., description="问卷提交记录ID")
