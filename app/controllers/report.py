import asyncio
import logging
import os
import re
from io import BytesIO
from typing import Dict, List, Optional

import pandas as pd
from openai import OpenAI
from PIL import Image as PILImage

from app.models.admin import AIProxy, AnalysisSheet, Document, OriginalSheet, Report, Skill, StaticFile, Workspace
from app.settings import settings
from app.utils.doc_to_md import file_to_markdown

logger = logging.getLogger(__name__)


class ReportService:
    @staticmethod
    def _build_client(ai_proxy) -> OpenAI:
        return OpenAI(base_url=ai_proxy.url, api_key=ai_proxy.token)

    @staticmethod
    async def _call_ai(client: OpenAI, model: str, system_prompt: str, user_prompt: str) -> str:
        def _sync_call():
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.7,
            )
            return response.choices[0].message.content
        return await asyncio.to_thread(_sync_call)

    @staticmethod
    def _format_size(size: int) -> str:
        if size < 1024:
            return f"{size} B"
        elif size < 1024 * 1024:
            return f"{size / 1024:.1f} KB"
        return f"{size / (1024 * 1024):.1f} MB"

    @classmethod
    def _short_link(cls, token: str) -> str:
        """构造完整短链接（含域名前缀，若 PUBLIC_BASE_URL 已配置）"""
        base = settings.PUBLIC_BASE_URL.rstrip("/") if settings.PUBLIC_BASE_URL else ""
        return f"{base}/api/sf/{token}"

    @classmethod
    def _generate_image_md(cls, rec) -> str:
        """为图片/静态文件生成元数据 Markdown 描述（不读取二进制内容）"""
        lines = [f"## {rec.name or getattr(rec, 'file_name', '文件')}"]
        if hasattr(rec, 'file_size') and rec.file_size:
            lines.append(f"- 大小: {cls._format_size(rec.file_size)}")
        if hasattr(rec, 'width') and rec.width and hasattr(rec, 'height') and rec.height:
            lines.append(f"- 尺寸: {rec.width}×{rec.height}px")
        if hasattr(rec, 'format_type') and rec.format_type:
            lines.append(f"- 格式: {rec.format_type}")
        if hasattr(rec, 'color_mode') and rec.color_mode:
            lines.append(f"- 色彩: {rec.color_mode}")
        if hasattr(rec, 'dpi') and rec.dpi:
            lines.append(f"- DPI: {rec.dpi}")
        if hasattr(rec, 'bit_depth') and rec.bit_depth:
            lines.append(f"- 位深: {rec.bit_depth}bit")
        if hasattr(rec, 'short_url_token') and rec.short_url_token:
            lines.append(f"- 短链接: `{cls._short_link(rec.short_url_token)}`")
        if hasattr(rec, 'description') and rec.description:
            lines.append(f"- 描述: {rec.description}")
        if hasattr(rec, 'source') and rec.source:
            source_labels = {
                "upload": "用户上传", "cv_processed": "CV处理",
                "ai_generated": "AI生成", "ocr": "OCR提取",
                "road_material": "路网素材", "auto": "自动生成",
            }
            lines.append(f"- 来源: {source_labels.get(rec.source, rec.source)}")
        return "\n".join(lines)

    @classmethod
    async def _read_all_data(cls, sheet_ids: List[int], analysis_ids: List[int], document_ids: List[int] = None, static_file_ids: List[int] = None) -> str:
        """异步读取所有数据源：表格（Excel/CSV） + 文档（PDF/DOCX/MD等） + 静态文件（图片元数据）"""
        if document_ids is None:
            document_ids = []
        if static_file_ids is None:
            static_file_ids = []

        tasks = []
        for sid in sheet_ids:
            tasks.append(OriginalSheet.get_or_none(id=sid))
        for aid in analysis_ids:
            tasks.append(AnalysisSheet.get_or_none(id=aid))
        for did in document_ids:
            tasks.append(Document.get_or_none(id=did))
        for sfid in static_file_ids:
            tasks.append(StaticFile.get_or_none(id=sfid))
        records = await asyncio.gather(*tasks)

        def _read_one(rec):
            if rec is None:
                return None
            try:
                # 获取记录名（兼容不同模型字段名）
                rec_name = getattr(rec, 'name', None) or getattr(rec, 'file_name', '文件')

                # 1. 图片/StaticFile：仅生成元数据描述
                is_static_image = hasattr(rec, 'is_image') and rec.is_image
                if is_static_image:
                    ext = os.path.splitext(getattr(rec, 'file_name', '') or getattr(rec, 'file_path', ''))[1].lower()
                    if ext in ('.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp', '.tiff', '.tif', '.svg'):
                        return ReportService._generate_image_md(rec)

                file_path = getattr(rec, 'file_path', None)
                if not file_path:
                    return None

                # 2. 文件不存在 → 友好占位
                if not os.path.exists(file_path):
                    logger.warning(f"文件不存在: {file_path}")
                    return f"## {rec_name}\n\n*(文件不存在: {os.path.basename(file_path)})*"

                ext = os.path.splitext(file_path)[1].lower()
                ext_name = os.path.basename(file_path)

                # 3. 图片扩展名 → 元数据描述
                if ext in ('.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp', '.tiff', '.tif'):
                    return ReportService._generate_image_md(rec)

                # 4. CSV → pandas read_csv
                if ext == '.csv':
                    df = pd.read_csv(file_path)
                    return f"## {rec_name}\n\n{df.head(80).to_markdown(index=False)}"

                # 5. Excel → pandas read_excel
                if ext in ('.xlsx', '.xls'):
                    df = pd.read_excel(file_path)
                    return f"## {rec_name}\n\n{df.head(80).to_markdown(index=False)}"

                # 6. 使用 doc_to_md 处理 PDF/DOCX/PPTX/MD/TXT 等
                try:
                    md_text, _ = file_to_markdown(file_path, ext_name)
                    return f"## {rec_name}\n\n{md_text[:5000]}"
                except ValueError:
                    # 不支持的格式 → 回退为文本模式（带容错）
                    try:
                        with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                            text = f.read()
                        return f"## {rec_name}\n\n{text[:5000]}"
                    except Exception:
                        # 二进制文件最后兜底 → 元数据描述
                        logger.warning(f"无法读取文件内容（二进制/未知格式）: {file_path}")
                        return ReportService._generate_image_md(rec)
            except Exception as e:
                logger.warning(f"读取文件失败 {getattr(rec, 'file_path', '?')}: {e}")
                return None

        parts = []
        for rec in records:
            result = await asyncio.to_thread(_read_one, rec)
            if result:
                parts.append(result)
        return "\n\n".join(parts) if parts else "（无数据源）"

    @classmethod
    async def generate_report(
        cls,
        workspace_id: int,
        name: str,
        sheet_ids: List[int],
        analysis_ids: List[int],
        ai_proxy_id: int,
        skill_id: Optional[int] = None,
        extra_prompt: str = "",
        document_ids: List[int] = None,
        static_file_ids: List[int] = None,
    ) -> Report:
        if document_ids is None:
            document_ids = []
        if static_file_ids is None:
            static_file_ids = []
        ai_proxy = await AIProxy.get(id=ai_proxy_id)
        skill_prompt = ""
        if skill_id:
            skill = await Skill.filter(id=skill_id).first()
            if skill:
                skill_prompt = skill.content

        data_text = await cls._read_all_data(sheet_ids, analysis_ids, document_ids, static_file_ids)

        system_prompt = """你是一个专业的数据分析报告生成专家。请根据提供的数据生成一份完整的HTML格式分析报告。
报告需包含以下部分（使用HTML标签）：
1. <h1> 报告标题
2. <h2> 数据概览 — 数据来源、数据量等
3. <h2> 核心发现 — 3-5个关键洞察
4. <h2> 详细分析 — 多维度数据解读，包含 <table> 表格
5. <h2> 结论与建议
样式要求：使用内联CSS，简洁专业风格，配色为蓝白灰。"""

        if skill_prompt:
            system_prompt += f"\n\n报告框架参考：\n{skill_prompt}"

        user_prompt = f"报告标题：{name}\n\n数据来源：\n{data_text}"
        if extra_prompt:
            user_prompt += f"\n\n额外要求：{extra_prompt}"
        user_prompt += "\n\n请生成完整的HTML报告（包含<!DOCTYPE html>声明），直接返回HTML代码。"

        client = cls._build_client(ai_proxy)
        html_content = await cls._call_ai(client, ai_proxy.model or "gpt-3.5-turbo", system_prompt, user_prompt)
        html_content = cls._clean_html(html_content)

        report = await Report.create(
            workspace_id=workspace_id,
            name=name,
            content=html_content,
            source_sheet_ids=sheet_ids,
            source_analysis_ids=analysis_ids,
            source_document_ids=document_ids,
            source_static_ids=static_file_ids,
            ai_proxy_id=ai_proxy_id,
            skill_id=skill_id,
            prompt=extra_prompt,
        )
        return report

    @staticmethod
    def _clean_html(text: str) -> str:
        """从 AI 返回内容中提取纯 HTML 文档，丢弃所有非 HTML 的说明文本。"""
        text = text.strip()
        # 去除 markdown 代码块标记
        if text.startswith("```html"):
            text = text[7:]
        elif text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()

        # 提取 HTML 文档边界：从 <!DOCTYPE 或 <html 到 </html>
        html_start = -1
        html_end = -1

        doctype_idx = text.lower().find("<!doctype")
        html_tag_idx = text.lower().find("<html")
        if doctype_idx != -1:
            html_start = doctype_idx
        elif html_tag_idx != -1:
            html_start = html_tag_idx

        if html_start != -1:
            end_idx = text.lower().rfind("</html>")
            if end_idx != -1:
                html_end = end_idx + len("</html>")

        if html_start != -1 and html_end != -1:
            text = text[html_start:html_end]

        # 如果没有 <!DOCTYPE 但有 <html，补充 DOCTYPE 声明
        if text.strip().lower().startswith("<html"):
            text = "<!DOCTYPE html>\n" + text

        return text.strip()

    @classmethod
    async def export_html(cls, report_id: int) -> str:
        report = await Report.get(id=report_id)
        return report.content

    @classmethod
    async def export_pdf_bytes(cls, report_id: int) -> bytes:
        try:
            from weasyprint import HTML
            report = await Report.get(id=report_id)
            html = HTML(string=report.content)
            return html.write_pdf()
        except ImportError:
            raise RuntimeError("weasyprint 未安装")

    @classmethod
    async def export_docx_bytes(cls, report_id: int) -> bytes:
        try:
            from docx import Document
            from bs4 import BeautifulSoup
            report = await Report.get(id=report_id)
            soup = BeautifulSoup(report.content, "html.parser")

            doc = Document()
            for tag in soup.find_all(["h1", "h2", "h3", "h4", "p", "table", "ul", "ol"]):
                if tag.name == "h1":
                    doc.add_heading(tag.get_text(), level=1)
                elif tag.name == "h2":
                    doc.add_heading(tag.get_text(), level=2)
                elif tag.name == "h3":
                    doc.add_heading(tag.get_text(), level=3)
                elif tag.name in ("p",):
                    doc.add_paragraph(tag.get_text())
                elif tag.name == "table":
                    rows = tag.find_all("tr")
                    if rows:
                        table = doc.add_table(rows=len(rows), cols=len(rows[0].find_all(["td", "th"])))
                        for i, row in enumerate(rows):
                            for j, cell in enumerate(row.find_all(["td", "th"])):
                                table.cell(i, j).text = cell.get_text()
                elif tag.name in ("ul", "ol"):
                    for li in tag.find_all("li"):
                        doc.add_paragraph(li.get_text(), style="List Bullet")

            buf = BytesIO()
            doc.save(buf)
            return buf.getvalue()
        except ImportError:
            raise RuntimeError("python-docx 未安装")

    # ── 数据源预览 ──

    @staticmethod
    def _estimate_tokens(text: str) -> int:
        """粗略估算 token 数：中文每字 ~1.5 token，英文每词 ~1.3 token"""
        chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
        english_words = len(re.findall(r'[a-zA-Z]+', text))
        other = max(0, len(text) - chinese_chars - sum(len(w) for w in re.findall(r'[a-zA-Z]+', text)))
        return int(chinese_chars * 1.5 + english_words * 1.3 + other * 0.3)

    @classmethod
    async def preview_sources(
        cls,
        sheet_ids: List[int],
        analysis_ids: List[int],
        document_ids: List[int],
        static_file_ids: List[int],
    ) -> dict:
        items = []
        md_parts = []

        # 1. 原始表格
        for sid in sheet_ids:
            sheet = await OriginalSheet.get_or_none(id=sid)
            if not sheet:
                continue
            try:
                ext = os.path.splitext(sheet.file_path)[1].lower() if sheet.file_path else ''
                if ext in ('.xlsx', '.xls', '.csv'):
                    df = pd.read_excel(sheet.file_path) if ext != '.csv' else pd.read_csv(sheet.file_path)
                    md_table = df.head(30).to_markdown(index=False)
                    preview = f"**{sheet.name}** ({cls._format_size(sheet.file_size or 0)})\n\n{md_table}\n\n*共 {len(df)} 行 × {len(df.columns)} 列*"
                else:
                    try:
                        text, _ = file_to_markdown(sheet.file_path, os.path.basename(sheet.file_path))
                        preview = f"**{sheet.name}** ({cls._format_size(sheet.file_size or 0)})\n\n{text[:3000]}"
                    except (ValueError, Exception):
                        try:
                            with open(sheet.file_path, 'r', encoding='utf-8', errors='replace') as f:
                                text = f.read()[:3000]
                        except Exception:
                            text = f"*（无法预览）*"
                        preview = f"**{sheet.name}** ({cls._format_size(sheet.file_size or 0)})\n\n```\n{text}\n```"
                items.append({
                    "id": sheet.id, "name": sheet.name, "type": "sheet",
                    "preview": preview, "char_count": len(preview),
                    "file_size": sheet.file_size or 0,
                })
                md_parts.append(preview)
            except Exception as e:
                logger.warning(f"预览表格失败 {sheet.file_path}: {e}")

        # 2. 分析表格
        for aid in analysis_ids:
            analysis = await AnalysisSheet.get_or_none(id=aid)
            if not analysis:
                continue
            try:
                ext = os.path.splitext(analysis.file_path)[1].lower() if analysis.file_path else ''
                if ext in ('.xlsx', '.xls', '.csv'):
                    df = pd.read_excel(analysis.file_path) if ext != '.csv' else pd.read_csv(analysis.file_path)
                    md_table = df.head(30).to_markdown(index=False)
                    preview = f"**{analysis.name}** ({cls._format_size(analysis.file_size or 0)})\n\n{md_table}\n\n*共 {len(df)} 行 × {len(df.columns)} 列*"
                else:
                    try:
                        text, _ = file_to_markdown(analysis.file_path, os.path.basename(analysis.file_path))
                        preview = f"**{analysis.name}** ({cls._format_size(analysis.file_size or 0)})\n\n{text[:3000]}"
                    except (ValueError, Exception):
                        try:
                            with open(analysis.file_path, 'r', encoding='utf-8', errors='replace') as f:
                                text = f.read()[:3000]
                        except Exception:
                            text = f"*（无法预览）*"
                        preview = f"**{analysis.name}** ({cls._format_size(analysis.file_size or 0)})\n\n```\n{text}\n```"
                items.append({
                    "id": analysis.id, "name": analysis.name, "type": "analysis",
                    "preview": preview, "char_count": len(preview),
                    "file_size": analysis.file_size or 0,
                })
                md_parts.append(preview)
            except Exception as e:
                logger.warning(f"预览分析表格失败 {analysis.file_path}: {e}")

        # 3. 文档
        for did in document_ids:
            doc = await Document.get_or_none(id=did)
            if not doc:
                continue
            try:
                if doc.file_path and os.path.exists(doc.file_path):
                    ext = os.path.splitext(doc.file_path)[1].lower()
                    ext_name = os.path.basename(doc.file_path)
                    if ext in ('.xlsx', '.xls', '.csv'):
                        df = pd.read_excel(doc.file_path) if ext != '.csv' else pd.read_csv(doc.file_path)
                        text = df.head(50).to_markdown(index=False)
                    elif ext in ('.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp', '.tiff', '.tif'):
                        # 图片文件 → 简短元数据描述
                        text = f"*（图片文件: {ext_name}）*"
                    else:
                        # 使用 doc_to_md 处理 PDF/DOCX/PPTX/MD/TXT 等
                        try:
                            text, _ = file_to_markdown(doc.file_path, ext_name)
                            text = text[:5000]
                        except ValueError:
                            try:
                                with open(doc.file_path, 'r', encoding='utf-8', errors='replace') as f:
                                    text = f.read()[:5000]
                            except Exception:
                                text = f"*（无法预览: {ext_name}）*"
                else:
                    text = f"*（空文档）*"
                preview_header = f"**{doc.name}**"
                if doc.file_size:
                    preview_header += f" ({cls._format_size(doc.file_size)})"
                if doc.char_count:
                    preview_header += f" — {doc.char_count} 字"
                if doc.import_source and doc.import_source != 'upload':
                    preview_header += f" — 来源: {doc.import_source}"
                if doc.row_count:
                    preview_header += f" — {doc.row_count} 行"
                preview = f"{preview_header}\n\n{text}"
                items.append({
                    "id": doc.id, "name": doc.name, "type": "document",
                    "preview": preview, "char_count": len(preview),
                    "file_size": doc.file_size or 0,
                })
                md_parts.append(preview)
            except Exception as e:
                logger.warning(f"预览文档失败 {doc.file_path}: {e}")

        # 4. 静态文件
        for sfid in static_file_ids:
            sf = await StaticFile.get_or_none(id=sfid)
            if not sf:
                continue
            try:
                lines = [f"**{sf.name or sf.file_name}**"]
                if sf.file_size:
                    lines.append(f"- 大小: {cls._format_size(sf.file_size)}")
                if sf.short_url_token:
                    lines.append(f"- 链接: `{cls._short_link(sf.short_url_token)}`")
                if sf.is_image and sf.width and sf.height:
                    lines.append(f"- 尺寸: {sf.width}×{sf.height}px")
                if sf.format_type:
                    lines.append(f"- 格式: {sf.format_type}")
                if sf.color_mode:
                    lines.append(f"- 色彩: {sf.color_mode}")
                if sf.dpi:
                    lines.append(f"- DPI: {sf.dpi}")
                if sf.bit_depth:
                    lines.append(f"- 位深: {sf.bit_depth}bit")
                if sf.description:
                    lines.append(f"- 描述: {sf.description}")
                if sf.source:
                    source_labels = {
                        "upload": "用户上传", "cv_processed": "CV处理",
                        "ai_generated": "AI生成", "ocr": "OCR提取",
                        "road_material": "路网素材", "auto": "自动生成",
                    }
                    lines.append(f"- 来源: {source_labels.get(sf.source, sf.source)}")
                if sf.exif_data:
                    exif_preview = {k: v for k, v in sf.exif_data.items() if v}
                    if exif_preview:
                        lines.append(f"- EXIF: {exif_preview}")
                preview = "\n".join(lines)
                items.append({
                    "id": sf.id, "name": sf.name or sf.file_name, "type": "static_file",
                    "preview": preview, "char_count": len(preview),
                    "file_size": sf.file_size or 0,
                })
                md_parts.append(preview)
            except Exception as e:
                logger.warning(f"预览静态文件失败 {sf.file_path}: {e}")

        # 构建完整的 MD 预览
        md_full = "\n\n---\n\n".join(md_parts) if md_parts else "（无数据源）"
        total_chars = sum(it["char_count"] for it in items)
        estimated_tokens = cls._estimate_tokens(md_full)

        return {
            "md_preview": md_full,
            "items": items,
            "total_chars": total_chars,
            "estimated_tokens": estimated_tokens,
            "source_counts": {
                "sheets": len([it for it in items if it["type"] == "sheet"]),
                "analyses": len([it for it in items if it["type"] == "analysis"]),
                "documents": len([it for it in items if it["type"] == "document"]),
                "static_files": len([it for it in items if it["type"] == "static_file"]),
                "total": len(items),
            },
        }


report_service = ReportService()