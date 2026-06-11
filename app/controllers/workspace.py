import asyncio
import io
import json
import logging
import os
import re
import uuid
from typing import Dict, List, Optional, Tuple

import pandas as pd
import numpy as np
from fastapi import UploadFile
from openai import OpenAI

from app.models.admin import AnalysisSheet, OriginalSheet, Skill, Workspace
from app.settings import settings

logger = logging.getLogger(__name__)

UPLOAD_DIR = os.path.join(settings.BASE_DIR, "uploads", "sheets")


class WorkspaceController:
    model = Workspace

    @classmethod
    async def get_accessible(cls, user_id: int, page: int, page_size: int):
        total = await cls.model.filter(users__id=user_id).count()
        objs = await (
            cls.model.filter(users__id=user_id)
            .offset((page - 1) * page_size)
            .limit(page_size)
            .order_by("-updated_at")
            .prefetch_related("users")
        )
        return total, objs

    @classmethod
    async def check_permission(cls, workspace_id: int, user_id: int):
        return await cls.model.filter(id=workspace_id, users__id=user_id).first()

    @classmethod
    async def update_users(cls, workspace: Workspace, user_ids: List[int]):
        from app.models.admin import User
        await workspace.users.clear()
        for uid in user_ids:
            user = await User.filter(id=uid).first()
            if user:
                await workspace.users.add(user)


class SheetService:
    """表格文件 I/O 服务：上传、读取、提取、保存"""

    @staticmethod
    def _ensure_dir():
        os.makedirs(UPLOAD_DIR, exist_ok=True)

    @staticmethod
    async def upload_sheet(workspace_id: int, file: UploadFile) -> OriginalSheet:
        SheetService._ensure_dir()
        ext = os.path.splitext(file.filename or "data.xlsx")[1] or ".xlsx"
        filename = f"{uuid.uuid4().hex}{ext}"
        filepath = os.path.join(UPLOAD_DIR, filename)
        content = await file.read()
        with open(filepath, "wb") as f:
            f.write(content)
        sheet = await OriginalSheet.create(
            workspace_id=workspace_id,
            name=file.filename or "未命名",
            file_path=filepath,
            file_size=len(content),
        )
        return sheet

    @staticmethod
    def read_excel(filepath: str) -> pd.DataFrame:
        """从文件路径读取 Excel 为 DataFrame"""
        return pd.read_excel(filepath)

    # ── Step 1: Excel → CSV 文本 + 表头提取 ──────────────────────

    @staticmethod
    def extract_table_info(
        filepath: str,
        max_sample_rows: int = 5,
        max_csv_rows: Optional[int] = None,
    ) -> dict:
        """
        提取表格信息，返回 CSV 文本 + 表头元信息 + 样本数据。

        返回结构:
        {
            "csv_text": str,        # 完整 CSV 文本（pd.to_csv 输出，无 index）
            "sample_csv": str,      # 前 max_sample_rows 行 CSV
            "sample_json": list,    # 前 max_sample_rows 行 list[dict]
            "columns": list[dict],  # 每列: {name, dtype, null_count, samples[...]}
            "shape": [rows, cols],
        }
        """
        df = pd.read_excel(filepath)

        # ── 构建列元信息 ──
        columns = []
        for col in df.columns:
            series = df[col]
            dtype = str(series.dtype)
            col_info = {
                "name": str(col),
                "dtype": dtype,
                "null_count": int(series.isna().sum()),
                "samples": [
                    str(v) for v in series.dropna().head(max_sample_rows).tolist()
                ],
            }
            # 数值列补充统计信息
            if pd.api.types.is_numeric_dtype(series) and series.notna().any():
                col_info["min"] = float(series.min())
                col_info["max"] = float(series.max())
                col_info["mean"] = round(float(series.mean()), 2)
            columns.append(col_info)

        # ── 截取行数（可选限制，防止超大文件撑爆内存） ──
        work_df = df.head(max_csv_rows) if max_csv_rows else df

        # ── 生成完整 CSV 文本 ──
        csv_text = work_df.to_csv(index=False)

        # ── 生成样本 CSV（前 max_sample_rows 行） ──
        sample_csv = df.head(max_sample_rows).to_csv(index=False)

        # ── 生成样本 JSON（前 max_sample_rows 行） ──
        sample_json = json.loads(
            df.head(max_sample_rows).to_json(orient="records", force_ascii=False)
        )

        return {
            "csv_text": csv_text,
            "sample_csv": sample_csv,
            "sample_json": sample_json,
            "columns": columns,
            "shape": [len(work_df), len(work_df.columns)],
        }

    # ── Step 5: JSON dict → 多个 Excel 文件 ──────────────────────

    @staticmethod
    def save_separate_results(
        base_name: str, sheet_dfs: Dict[str, pd.DataFrame]
    ) -> List[Tuple[str, str, int]]:
        """将多个 DataFrame 分别保存为 Excel 文件，返回 [(名称, 路径, 文件大小), ...]"""
        SheetService._ensure_dir()
        results = []
        for dimension_name, df in sheet_dfs.items():
            safe_dim = dimension_name.replace("/", "-")[:50]
            filename = f"{uuid.uuid4().hex}_{safe_dim}.xlsx"
            filepath = os.path.join(UPLOAD_DIR, filename)
            df.to_excel(filepath, index=False)
            file_size = os.path.getsize(filepath)
            results.append((f"{base_name}-{dimension_name}", filepath, file_size))
        return results


class AIAnalysisService:
    """AI 数据分析服务：脚本生成 → 执行 → 结果解析"""

    # 预置到 AI 脚本运行环境中的变量
    SCRIPT_PRESET = {"pd": pd, "np": np, "io": io, "json": json, "re": re}

    # ── AI 客户端 ───────────────────────────────────────────────

    @staticmethod
    def _build_client(ai_proxy) -> OpenAI:
        return OpenAI(base_url=ai_proxy.url, api_key=ai_proxy.token)

    @staticmethod
    async def _call_ai(
        client: OpenAI, model: str, system_prompt: str, user_prompt: str
    ) -> str:
        """异步调用 AI（openai SDK 同步阻塞 → 线程池执行）"""
        def _sync_call():
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.3,
            )
            return response.choices[0].message.content
        return await asyncio.to_thread(_sync_call)

    @staticmethod
    async def _get_skill_prompt(skill_id: Optional[int]) -> str:
        if not skill_id:
            return ""
        skill = await Skill.filter(id=skill_id).first()
        return skill.content if skill else ""

    # ── Step 2: AI 脚本生成 ─────────────────────────────────────

    @classmethod
    def _csv_parse_helper(cls) -> str:
        """返回 CSV 解析提示（注入 system prompt）"""
        return """
CSV 数据解析方法（pd, io 已预置，无需 import）：
```python
# csv_text 是标准 CSV 格式文本，pd.read_csv 可直接解析
df = pd.read_csv(io.StringIO(csv_text))
# 所有列的类型由 pandas 自动推断，数值列已是 int/float
```
"""

    @classmethod
    def _script_prompt(cls) -> str:
        """单表分析的脚本生成提示"""
        return """
请根据列信息和样本数据，生成 `analyze(csv_text)` 函数。

函数签名：`def analyze(csv_text: str) -> dict`

- csv_text: 标准 CSV 格式的完整表格数据（含表头行）
- 返回值: dict，键为分析维度名（如 "按地区汇总"、"按月份趋势"），值为 list[dict]
  （每个 dict 是一行数据，键是列名，值需确保 JSON 可序列化）

要求：
1. 所有需要的模块（pd, np, io, json, re）已预置，直接使用，禁止 import
2. 使用 pd.read_csv(io.StringIO(csv_text)) 解析数据
3. 使用 df.copy()、groupby、agg、value_counts 等进行统计分析
4. 每个分析结果用 df.to_dict("records") 转为 list[dict] 放入返回 dict
5. 确保所有值都是 JSON 可序列化的（将 numpy int64/float64 转为 Python int/float）
6. 返回纯代码，不要包裹在 ``` 中，不要解释
"""

    @classmethod
    def _script_prompt_correlate(cls) -> str:
        """关联分析的脚本生成提示"""
        return """
请生成 `analyze(csv_a: str, csv_b: str) -> dict` 函数，分析两个表的关联关系。

函数签名：`def analyze(csv_a: str, csv_b: str) -> dict`

- csv_a, csv_b: 两个标准 CSV 格式的表格数据
- 返回值: dict，键为分析维度名，值为 list[dict]

要求：
1. 使用 pd.read_csv(io.StringIO(...)) 分别解析两个 CSV
2. 使用 pd.merge() 按共有列关联，分析关联覆盖率、匹配率等
3. 每个结果用 df.to_dict("records") 转为 list[dict]
4. 确保所有值 JSON 可序列化
5. 返回纯代码，不要包裹在 ``` 中
"""

    @classmethod
    async def _generate_script(
        cls,
        table_info: dict,
        ai_proxy,
        skill_prompt: str = "",
        extra_prompt: str = "",
        is_correlation: bool = False,
    ) -> str:
        """
        Step 2: 将表头信息 + 样本数据 + Skill 发给 AI，生成分析脚本。

        table_info 包含:
        - columns: list[dict]  列元信息
        - sample_json: list    前 N 行 JSON 样本
        - sample_csv: str      前 N 行 CSV 样本
        - shape: [rows, cols]
        """
        # ── 构建 system prompt ──
        system_prompt = (
            "你是 Python 数据分析脚本专家。"
            "根据提供的列信息和样本数据，生成可直接执行的 pandas 分析代码。\n"
        )
        system_prompt += cls._csv_parse_helper()
        if skill_prompt:
            system_prompt += f"\n## 分析框架（Skill）\n{skill_prompt}"

        # ── 构建 user prompt：列信息 + 样本数据 JSON ──
        header_info = {
            "columns": table_info["columns"],
            "shape": table_info["shape"],
        }
        user_prompt = (
            f"## 列信息\n```json\n"
            f"{json.dumps(header_info, ensure_ascii=False, indent=2)}\n"
            f"```\n"
        )

        # 追加前 N 行样本数据（JSON 格式，AI 可直观理解数据内容）
        sample = table_info.get("sample_json", [])
        if sample:
            user_prompt += (
                f"\n## 样本数据（前 {len(sample)} 行）\n```json\n"
                f"{json.dumps(sample, ensure_ascii=False, indent=2)}\n"
                f"```\n"
            )

        if extra_prompt:
            user_prompt += f"\n## 额外要求\n{extra_prompt}\n"

        user_prompt += (
            cls._script_prompt_correlate() if is_correlation else cls._script_prompt()
        )

        client = cls._build_client(ai_proxy)
        code = await cls._call_ai(
            client, ai_proxy.model or "gpt-3.5-turbo", system_prompt, user_prompt
        )
        return cls._clean_code(code)

    @staticmethod
    def _clean_code(text: str) -> str:
        """清理 AI 返回的代码：去 ``` 包裹、去首尾空白"""
        text = text.strip()
        for prefix in ("```python", "```"):
            if text.startswith(prefix):
                text = text[len(prefix):].lstrip()
        if text.endswith("```"):
            text = text[:-3]
        return text.strip()

    # ── Step 3 & 4: 脚本执行 + JSON 结果解析 ─────────────────────

    @staticmethod
    def _validate_code(code: str) -> Optional[str]:
        """安全校验（当前已跳过）"""
        return None

    @classmethod
    def _execute_script(
        cls, code: str, *csv_texts: str
    ) -> Dict[str, pd.DataFrame]:
        """
        Step 3 & 4: 执行 AI 脚本，传入 CSV 文本，得到 JSON dict → DataFrame。

        参数:
        - code: AI 生成的 Python 代码（须定义 analyze 函数）
        - *csv_texts: 一个或多个 CSV 文本（单表 1 个，关联分析 2 个）

        返回:
        - dict[str, pd.DataFrame]: 分析维度名 → 结果 DataFrame
        """
        # ── 编译 ──
        try:
            compiled = compile(code, "<ai_script>", "exec")
        except SyntaxError as e:
            logger.error(f"脚本语法错误: {e}")
            return {"语法错误": pd.DataFrame({"错误": [str(e)]})}

        # ── 受限执行环境（保留 __import__ 供 pandas/numpy 内部 C 扩展使用） ──
        restricted_globals = {
            "__builtins__": {
                "__import__": __import__,  # pandas/numpy C 扩展内部需要
                "print": print, "len": len, "range": range, "enumerate": enumerate,
                "zip": zip, "sorted": sorted, "list": list, "dict": dict, "set": set,
                "int": int, "float": float, "str": str, "bool": bool, "type": type,
                "isinstance": isinstance, "abs": abs, "round": round,
                "min": min, "max": max, "sum": sum, "any": any, "all": all,
                "Exception": Exception, "ValueError": ValueError,
                "TypeError": TypeError, "KeyError": KeyError, "IndexError": IndexError,
            },
            **cls.SCRIPT_PRESET,
        }
        local_vars = {}

        try:
            exec(compiled, restricted_globals, local_vars)
        except Exception as e:
            logger.error(f"脚本执行错误: {e}")
            return {"执行错误": pd.DataFrame({"错误": [str(e)]})}

        # ── 调用 analyze 函数 ──
        analyze_func = local_vars.get("analyze")
        if not analyze_func:
            return {"缺少函数": pd.DataFrame({"提示": ["未定义 analyze(csv_text) 函数"]})}

        try:
            json_result = analyze_func(*csv_texts)
        except Exception as e:
            import traceback
            logger.error(f"analyze() 调用错误: {e}")
            return {
                "调用错误": pd.DataFrame(
                    {"错误": [f"{e}\n{traceback.format_exc()}"]}
                )
            }

        # ── Step 4: JSON dict → dict[str, pd.DataFrame] ──
        return cls._json_to_sheets(json_result)

    @staticmethod
    def _json_to_sheets(result: dict) -> Dict[str, pd.DataFrame]:
        """
        将 analyze() 返回的 JSON dict 转为 DataFrame dict。

        支持的值格式:
        - list[dict] → DataFrame（推荐）
        - pd.DataFrame → 直接使用
        - list[scalar] → 单列 DataFrame
        - 其他 → 单行文本 DataFrame
        """
        if not isinstance(result, dict):
            return {"原始输出": pd.DataFrame({"内容": [str(result)]})}

        sheets = {}
        for name, data in result.items():
            key = str(name)
            if isinstance(data, list) and len(data) > 0 and isinstance(data[0], dict):
                sheets[key] = pd.DataFrame(data)
            elif isinstance(data, pd.DataFrame):
                sheets[key] = data
            elif isinstance(data, list):
                sheets[key] = pd.DataFrame({"值": data})
            else:
                sheets[key] = pd.DataFrame({"内容": [str(data)]})

        return sheets if sheets else {"空结果": pd.DataFrame({"提示": ["未生成有效数据"]})}

    # ── 单表分析入口 ────────────────────────────────────────────

    @classmethod
    async def analyze_sheet(
        cls,
        workspace_id: int,
        sheet_id: int,
        ai_proxy_id: int,
        name: str,
        skill_id: Optional[int] = None,
        extra_prompt: str = "",
    ) -> List[AnalysisSheet]:
        """
        完整分析流程:
        Step 1: Excel → CSV + 表头
        Step 2: 表头 + 样本 → AI 生成脚本
        Step 3: CSV 文本 → 脚本执行
        Step 4: JSON → DataFrame
        Step 5: DataFrame → 多个 Excel → DB 记录
        """
        from app.models.admin import AIProxy

        sheet = await OriginalSheet.get(id=sheet_id)
        ai_proxy = await AIProxy.get(id=ai_proxy_id)
        skill_prompt = await cls._get_skill_prompt(skill_id)

        # ── Step 1: 提取 CSV + 表头 + 样本 ──
        def _extract():
            return SheetService.extract_table_info(sheet.file_path)
        info = await asyncio.to_thread(_extract)

        # ── Step 2: AI 生成脚本（发送表头 + 样本 JSON） ──
        code = await cls._generate_script(
            table_info=info,
            ai_proxy=ai_proxy,
            skill_prompt=skill_prompt,
            extra_prompt=extra_prompt,
            is_correlation=False,
        )

        # ── Step 3 & 4: 执行脚本（传入 CSV 文本） ──
        csv_text = info["csv_text"]
        def _run():
            return cls._execute_script(code, csv_text)
        sheet_dfs = await asyncio.to_thread(_run)

        # ── Step 5: 保存为多个 Excel 文件 ──
        files = SheetService.save_separate_results(name, sheet_dfs)
        analyses = []
        for fname, fpath, fsize in files:
            analysis = await AnalysisSheet.create(
                workspace_id=workspace_id,
                name=fname,
                file_path=fpath,
                file_size=fsize,
                source_type="analysis",
                source_sheet_id=sheet_id,
                ai_proxy_id=ai_proxy_id,
                skill_id=skill_id,
                prompt=extra_prompt,
            )
            analyses.append(analysis)

        return analyses

    # ── 关联分析入口 ────────────────────────────────────────────

    @classmethod
    async def correlate_sheets(
        cls,
        workspace_id: int,
        sheet_a_id: int,
        sheet_b_id: int,
        ai_proxy_id: int,
        name: str,
        skill_id: Optional[int] = None,
        extra_prompt: str = "",
    ) -> List[AnalysisSheet]:
        """
        关联分析流程（两张表）:
        Step 1: 两张 Excel → 两份 CSV + 两份表头
        Step 2: 合并后的表头 + 样本 → AI 生成关联分析脚本
        Step 3: 两份 CSV → 脚本执行
        Step 4: JSON → DataFrame
        Step 5: DataFrame → 多个 Excel → DB 记录
        """
        from app.models.admin import AIProxy

        sheet_a = await OriginalSheet.get(id=sheet_a_id)
        sheet_b = await OriginalSheet.get(id=sheet_b_id)
        ai_proxy = await AIProxy.get(id=ai_proxy_id)
        skill_prompt = await cls._get_skill_prompt(skill_id)

        # ── Step 1: 分别提取 ──
        def _extract():
            a = SheetService.extract_table_info(sheet_a.file_path)
            b = SheetService.extract_table_info(sheet_b.file_path)
            return a, b
        info_a, info_b = await asyncio.to_thread(_extract)

        # ── 合并表头信息（标注来源） ──
        merged_columns = []
        for c in info_a["columns"]:
            merged_columns.append({**c, "source": "A"})
        for c in info_b["columns"]:
            merged_columns.append({**c, "source": "B"})

        merged_sample = []
        for row in info_a["sample_json"]:
            merged_sample.append({f"A.{k}": v for k, v in row.items()})
        for row in info_b["sample_json"]:
            merged_sample.append({f"B.{k}": v for k, v in row.items()})

        merged_info = {
            "columns": merged_columns,
            "sample_json": merged_sample,
            "sample_csv": (
                f"# ── 表格 A ──\n{info_a['sample_csv']}\n"
                f"# ── 表格 B ──\n{info_b['sample_csv']}"
            ),
            "shape": [
                info_a["shape"][0] + info_b["shape"][0],
                max(info_a["shape"][1], info_b["shape"][1]),
            ],
        }

        # ── Step 2: AI 生成关联分析脚本 ──
        code = await cls._generate_script(
            table_info=merged_info,
            ai_proxy=ai_proxy,
            skill_prompt=skill_prompt,
            extra_prompt=extra_prompt,
            is_correlation=True,
        )

        # ── Step 3 & 4: 执行脚本（传入两份 CSV） ──
        csv_a, csv_b = info_a["csv_text"], info_b["csv_text"]
        def _run():
            return cls._execute_script(code, csv_a, csv_b)
        sheet_dfs = await asyncio.to_thread(_run)

        # ── Step 5: 保存 ──
        files = SheetService.save_separate_results(name, sheet_dfs)
        analyses = []
        for fname, fpath, fsize in files:
            analysis = await AnalysisSheet.create(
                workspace_id=workspace_id,
                name=fname,
                file_path=fpath,
                file_size=fsize,
                source_type="correlation",
                source_sheet_id=sheet_a_id,
                related_sheet_id=sheet_b_id,
                ai_proxy_id=ai_proxy_id,
                skill_id=skill_id,
                prompt=extra_prompt,
            )
            analyses.append(analysis)

        return analyses


workspace_controller = WorkspaceController()
