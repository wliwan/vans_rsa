import asyncio
import logging
import os
from io import BytesIO
from typing import Dict, List, Optional

import pandas as pd
from openai import OpenAI

from app.models.admin import AIProxy, AnalysisSheet, OriginalSheet, Report, Skill, Workspace
from app.settings import settings

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

    @classmethod
    async def _read_all_data(cls, sheet_ids: List[int], analysis_ids: List[int]) -> str:
        """异步读取所有数据源：先异步查询记录，再线程池读 Excel"""
        tasks = []
        for sid in sheet_ids:
            tasks.append(OriginalSheet.get_or_none(id=sid))
        for aid in analysis_ids:
            tasks.append(AnalysisSheet.get_or_none(id=aid))
        records = await asyncio.gather(*tasks)

        def _read_one(rec):
            if rec is None:
                return None
            try:
                df = pd.read_excel(rec.file_path)
                return f"## {rec.name}\n\n{df.head(80).to_markdown(index=False)}"
            except Exception as e:
                logger.warning(f"读取文件失败 {rec.file_path}: {e}")
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
    ) -> Report:
        ai_proxy = await AIProxy.get(id=ai_proxy_id)
        skill_prompt = ""
        if skill_id:
            skill = await Skill.filter(id=skill_id).first()
            if skill:
                skill_prompt = skill.content

        data_text = await cls._read_all_data(sheet_ids, analysis_ids)

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
            ai_proxy_id=ai_proxy_id,
            skill_id=skill_id,
            prompt=extra_prompt,
        )
        return report

    @staticmethod
    def _clean_html(text: str) -> str:
        text = text.strip()
        if text.startswith("```html"):
            text = text[7:]
        elif text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        if "<!DOCTYPE" not in text.upper() and "<html" in text.lower():
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


report_service = ReportService()
