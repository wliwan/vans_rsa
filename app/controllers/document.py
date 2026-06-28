import asyncio
import logging
import os
import uuid
from typing import List, Optional

from fastapi import UploadFile

from app.models.admin import AIProxy, Document, Skill, Workspace
from app.utils.doc_to_md import file_to_markdown

logger = logging.getLogger(__name__)

UPLOAD_DIR = os.path.join("uploads", "documents")


class DocumentController:
    ALLOWED_EXTENSIONS = {".txt", ".md", ".markdown", ".pdf", ".docx", ".ppt", ".pptx", ".xlsx", ".xls", ".csv"}

    # ── CRUD ──

    @staticmethod
    async def list_by_workspace(workspace_id: int, source_type: Optional[str] = None):
        qs = Document.filter(workspace_id=workspace_id)
        if source_type:
            qs = qs.filter(source_type=source_type)
        return await qs.order_by("-created_at")

    @staticmethod
    async def get(document_id: int) -> Optional[Document]:
        return await Document.filter(id=document_id).first()

    @staticmethod
    async def upload(workspace_id: int, file: UploadFile) -> Document:
        ext = os.path.splitext(file.filename or "unknown")[1].lower()
        if ext not in DocumentController.ALLOWED_EXTENSIONS:
            raise ValueError(f"不支持的文件格式: {ext}，支持 {', '.join(DocumentController.ALLOWED_EXTENSIONS)}")

        os.makedirs(UPLOAD_DIR, exist_ok=True)
        unique_name = f"{uuid.uuid4().hex}_{file.filename}"
        file_path = os.path.join(UPLOAD_DIR, unique_name)

        content = await file.read()
        with open(file_path, "wb") as f:
            f.write(content)

        file_size = os.path.getsize(file_path)

        # 尝试转 MD 获取字符数
        try:
            _, char_count = file_to_markdown(file_path, file.filename or unique_name)
        except Exception:
            char_count = len(content.decode("utf-8", errors="replace")) if content else 0

        doc = await Document.create(
            workspace_id=workspace_id,
            name=file.filename or unique_name,
            file_path=file_path,
            file_size=file_size,
            char_count=char_count,
            source_type="original",
        )
        return doc

    @staticmethod
    async def create_from_text(workspace_id: int, name: str, content: str) -> Document:
        os.makedirs(UPLOAD_DIR, exist_ok=True)
        safe_name = name.replace("/", "_").replace("\\", "_")[:100]
        unique_name = f"{uuid.uuid4().hex}_{safe_name}.md"
        file_path = os.path.join(UPLOAD_DIR, unique_name)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)
        return await Document.create(
            workspace_id=workspace_id,
            name=name if name.endswith('.md') else name + '.md',
            file_path=file_path,
            file_size=os.path.getsize(file_path),
            char_count=len(content),
            source_type="original",
        )

    @staticmethod
    async def delete(document_id: int):
        from app.utils.file_utils import safe_delete_file
        doc = await Document.filter(id=document_id).first()
        if doc:
            await safe_delete_file(doc.file_path, Document, doc.id)
            await doc.delete()

    @staticmethod
    async def batch_delete(document_ids: List[int]):
        for did in document_ids:
            await DocumentController.delete(did)

    @staticmethod
    async def get_content(document_id: int) -> Optional[str]:
        doc = await Document.filter(id=document_id).first()
        if not doc or not doc.file_path or not os.path.exists(doc.file_path):
            return None
        with open(doc.file_path, "r", encoding="utf-8") as f:
            return f.read()

    @staticmethod
    async def update_content(document_id: int, content: str, name: Optional[str] = None) -> Optional[Document]:
        doc = await Document.filter(id=document_id).first()
        if not doc or not doc.file_path:
            return None
        with open(doc.file_path, "w", encoding="utf-8") as f:
            f.write(content)
        doc.char_count = len(content)
        doc.file_size = os.path.getsize(doc.file_path)
        if name is not None:
            doc.name = name
        await doc.save()
        return doc

    @staticmethod
    async def clear_by_workspace(workspace_id: int):
        from app.utils.file_utils import safe_delete_file
        docs = await Document.filter(workspace_id=workspace_id).all()
        for doc in docs:
            await safe_delete_file(doc.file_path, Document, doc.id)
        await Document.filter(workspace_id=workspace_id).delete()

    # ── AI 分析 ──

    @staticmethod
    async def ai_analyze(
        workspace_id: int,
        document_ids: List[int],
        ai_proxy_id: int,
        skill_id: Optional[int] = None,
        prompt: str = "",
    ):
        from openai import OpenAI

        # 1. 获取 AI 代理
        ai_proxy = await AIProxy.filter(id=ai_proxy_id).first()
        if not ai_proxy:
            raise ValueError("AI代理不存在")

        # 2. 获取 Skill 内容
        skill_content = ""
        if skill_id:
            skill = await Skill.filter(id=skill_id).first()
            if skill:
                skill_content = skill.content

        # 3. 读取并转换所有原始文档
        docs = await Document.filter(id__in=document_ids, workspace_id=workspace_id, source_type="original").all()
        if not docs:
            raise ValueError("未找到有效的原始文档")

        combined_md_parts = []
        for doc in docs:
            try:
                md_text, _ = file_to_markdown(doc.file_path, doc.name)
                combined_md_parts.append(f"## 文档: {doc.name}\n\n{md_text}")
            except Exception as e:
                logger.warning(f"文档转换失败 {doc.name}: {e}")

        combined_md = "\n\n---\n\n".join(combined_md_parts)

        # 4. 构建 prompt
        system_prompt = "你是一个文档分析助手。请根据提供的文档内容，生成一份结构化的分析报告（Markdown 格式）。"
        if skill_content:
            system_prompt += f"\n\n## 分析框架（Skill）\n{skill_content}"
        if prompt:
            system_prompt += f"\n\n## 用户额外要求\n{prompt}"

        # 5. 调用 AI
        client = OpenAI(base_url=ai_proxy.url, api_key=ai_proxy.token)
        model = ai_proxy.model or "gpt-3.5-turbo"

        def _sync_call():
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"以下是要分析的文档内容：\n\n{combined_md}"},
                ],
                temperature=0.7,
            )
            return response.choices[0].message.content

        result_md = await asyncio.to_thread(_sync_call)

        # 6. 保存分析结果
        source_names = "_".join([d.name.rsplit(".", 1)[0][:20] for d in docs[:3]])
        analysis_name = f"{source_names}_分析_{uuid.uuid4().hex[:8]}.md"
        os.makedirs(UPLOAD_DIR, exist_ok=True)
        analysis_path = os.path.join(UPLOAD_DIR, analysis_name)
        with open(analysis_path, "w", encoding="utf-8") as f:
            f.write(result_md)

        analysis_doc = await Document.create(
            workspace_id=workspace_id,
            name=analysis_name.replace(".md", ""),
            file_path=analysis_path,
            file_size=os.path.getsize(analysis_path),
            char_count=len(result_md),
            source_type="analysis",
            ai_proxy_id=ai_proxy_id,
            skill_id=skill_id,
            prompt=prompt,
        )
        return analysis_doc


document_controller = DocumentController()
