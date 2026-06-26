import asyncio
import datetime
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


    @staticmethod
    async def import_csv(workspace_id: int, name: str, csv_text: str) -> "OriginalSheet":
        """从 CSV 文本导入为原始表格"""
        SheetService._ensure_dir()
        safe_name = name if name.endswith(".csv") else f"{name}.csv"
        filename = f"{uuid.uuid4().hex}.csv"
        filepath = os.path.join(UPLOAD_DIR, filename)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(csv_text)
        file_size = os.path.getsize(filepath)
        sheet = await OriginalSheet.create(
            workspace_id=workspace_id,
            name=safe_name,
            file_path=filepath,
            file_size=file_size,
        )
        return sheet


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
    def _pandas_pitfalls(cls) -> str:
        """pandas 数据处理完整指南（从读取到输出，注入 system prompt）"""
        return """
## 📊 pandas 数据处理完整指南

所有需要的模块（pd, np, io, json, re）已预置，**禁止 import**。

---

### 1. 数据读取

```python
df = pd.read_csv(io.StringIO(csv_text))
# 立即检查数据概况，以选择后续处理策略：
# df.dtypes      → 各列推断类型
# df.head(3)     → 前几行数据样貌
# df.isna().sum() → 每列缺失值数量
```

**重要认知**：pandas 将含缺失值的整数列自动推断为 **float64**（因 NaN 是 IEEE 754 float 标准值）。
若样本数据某列全为整数但 `dtypes` 显示为 float，说明该列存在缺失值。

---

### 2. 数据清洗：按场景选择策略

#### 缺失值处理
| 场景 | 策略 | 示例 |
|------|------|------|
| 该列参与求和/均值 | `fillna(0)` 或跳过（agg 默认 skipna=True） | `df['金额'].fillna(0)` |
| 该列作为分组维度且需保留 | `fillna('未知')` | `df['分类'].fillna('未知')` |
| 直接删除含缺失行 | `dropna(subset=[...])` | `df.dropna(subset=['关键列'])` |
| 不处理，聚合时自动忽略 | 无需操作 | groupby/agg 默认 skipna=True |

#### 类型转换安全法则
- 目标为整数时，先处理 NaN：`df['col'].fillna(0).astype(int)` 或 `df['col'].astype('Int64')`
- 目标为字符串时，先转字符串再 fillna：`df['col'].astype(str).replace('nan', '')`
- 目标为 datetime 时：`pd.to_datetime(df['col'], errors='coerce')`

**禁止**：对含 NaN 的 float64 列直接调用 `.astype(int)` 或 Python `int()`，会抛出 `cannot convert float NaN to integer`。

---

### 3. 数据分析模式

#### 分组聚合（最常用）
```python
# ✅ 推荐：字典精确指定列与聚合函数，然后 reset_index 还原为普通列
result = (
    df.groupby('分组列')
      .agg({'数值列1': 'sum', '数值列2': 'mean', '文本列': 'count'})
      .reset_index()
)
# ❌ 避免：agg('sum') 不加区分地对所有列聚合（含非数值列会产出 NaN 列）
```

支持的聚合函数：`sum`, `mean`, `count`, `min`, `max`, `std`, `median`, `first`, `last`, `nunique`。

#### 透视表
```python
# ✅ 用 pd.pivot_table（支持聚合）
result = pd.pivot_table(df, values='c', index='a', columns='b', aggfunc='sum', fill_value=0)
# ❌ 禁止 df.pivot()——不支持聚合，重复索引会报错
```

#### 排序
```python
df_sorted = df.sort_values('排序列', ascending=False)
```

#### 关联分析（两张表时）
```python
df_a = pd.read_csv(io.StringIO(csv_a))
df_b = pd.read_csv(io.StringIO(csv_b))
merged = pd.merge(df_a, df_b, on='共同列', how='inner')  # 或 left/right/outer
```

---

### 4. 输出安全：JSON 序列化

`to_dict('records')` 返回的 Python 对象可能包含 numpy 标量，必须转为 JSON 兼容类型。

**推荐统一使用 `_safe_value()` 辅助函数**（定义一个即可）：

```python
import math

def _safe_value(v):
    \"\"\"将任意值转为 JSON 可序列化的 Python 原生类型\"\"\"
    if v is None:
        return None
    if isinstance(v, (np.integer,)):
        return int(v)
    if isinstance(v, (np.floating,)):
        if pd.isna(v):
            return None       # NaN → JSON null
        if v == int(v):
            return int(v)     # 1.0 → 1（更干净）
        return float(v)
    if isinstance(v, (np.bool_,)):
        return bool(v)
    if isinstance(v, (np.datetime64,)):
        return str(v)
    if isinstance(v, float) and math.isnan(v):
        return None
    if isinstance(v, (np.ndarray,)):
        return v.tolist()
    return v

# 用法：统一清洗每一行
result = [
    {k: _safe_value(v) for k, v in row.items()}
    for row in df.to_dict('records')
]
```

**返回值 dict 格式**：`{"分析维度名": list_of_dicts, ...}`，每个 list 中的 dict 即数据行。

---

### 5. 禁止使用的 API

- `inplace=True` — pandas 2.0+ 已弃用
- `df.append()` — pandas 2.0 已移除，用 `pd.concat([df1, df2])` 替代
- `df.ix[]` — 已移除多年，用 `.loc[]` 或 `.iloc[]`
- `pd.NaT` 直接比较 — 用 `pd.isna()` 判断
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
        if skill_prompt:
            system_prompt += f"\n## 分析框架（Skill）\n{skill_prompt}"
        system_prompt += cls._pandas_pitfalls()

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
                "zip": zip, "map": map, "filter": filter, "sorted": sorted,
                "list": list, "dict": dict, "set": set, "tuple": tuple,
                "int": int, "float": float, "str": str, "bool": bool, "type": type,
                "isinstance": isinstance, "abs": abs, "round": round,
                "min": min, "max": max, "sum": sum, "any": any, "all": all,
                "next": next, "iter": iter, "reversed": reversed,
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


    # ── 分析表格间关联分析 ─────────────────────────────────────

    @classmethod
    async def correlate_analyses(
        cls,
        workspace_id: int,
        analysis_a_id: int,
        analysis_b_id: int,
        ai_proxy_id: int,
        name: str,
        skill_id: Optional[int] = None,
        extra_prompt: str = "",
    ) -> List[AnalysisSheet]:
        """
        分析表格之间的关联分析流程:
        Step 1: 两份分析 Excel → 两份 CSV + 两份表头
        Step 2: 合并后的表头 + 样本 → AI 生成关联分析脚本
        Step 3: 两份 CSV → 脚本执行
        Step 4: JSON → DataFrame
        Step 5: DataFrame → 多个 Excel → DB 记录
        """
        from app.models.admin import AIProxy

        analysis_a = await AnalysisSheet.get(id=analysis_a_id)
        analysis_b = await AnalysisSheet.get(id=analysis_b_id)
        ai_proxy = await AIProxy.get(id=ai_proxy_id)
        skill_prompt = await cls._get_skill_prompt(skill_id)

        # ── Step 1: 分别提取 ──
        def _extract():
            a = SheetService.extract_table_info(analysis_a.file_path)
            b = SheetService.extract_table_info(analysis_b.file_path)
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
                f"# ── 分析表格 A ──\n{info_a['sample_csv']}\n"
                f"# ── 分析表格 B ──\n{info_b['sample_csv']}"
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
                source_sheet_id=None,
                related_sheet_id=None,
                ai_proxy_id=ai_proxy_id,
                skill_id=skill_id,
                prompt=extra_prompt,
            )
            analyses.append(analysis)

        return analyses


class CopyService:
    """跨工作区复制数据"""

    @staticmethod
    async def copy_to_workspace(
        target_workspace_id: int,
        sheet_ids: List[int],
        analysis_ids: List[int],
        document_ids: List[int],
        static_file_ids: List[int],
    ) -> dict:
        from app.models.admin import Document, StaticFile
        copied = {"sheets": 0, "analyses": 0, "documents": 0, "static_files": 0}

        # 复制原始表格
        for sid in sheet_ids:
            src = await OriginalSheet.filter(id=sid).first()
            if src:
                await OriginalSheet.create(
                    workspace_id=target_workspace_id,
                    name=src.name,
                    file_path=src.file_path,
                    file_size=src.file_size,
                )
                copied["sheets"] += 1

        # 复制分析表格
        for aid in analysis_ids:
            src = await AnalysisSheet.filter(id=aid).first()
            if src:
                await AnalysisSheet.create(
                    workspace_id=target_workspace_id,
                    name=src.name,
                    file_path=src.file_path,
                    file_size=src.file_size,
                    source_type=src.source_type,
                    ai_proxy_id=src.ai_proxy_id,
                    skill_id=src.skill_id,
                    prompt=src.prompt,
                )
                copied["analyses"] += 1

        # 复制文档
        for did in document_ids:
            src = await Document.filter(id=did).first()
            if src:
                await Document.create(
                    workspace_id=target_workspace_id,
                    name=src.name,
                    file_path=src.file_path,
                    file_size=src.file_size,
                    char_count=src.char_count,
                    source_type=src.source_type,
                    import_source=src.import_source,
                    source_table=src.source_table,
                    row_count=src.row_count,
                    dump_date=src.dump_date,
                    source_last_updated=src.source_last_updated,
                    ai_proxy_id=src.ai_proxy_id,
                    skill_id=src.skill_id,
                    prompt=src.prompt,
                )
                copied["documents"] += 1

        # 复制静态文件（仅创建数据库记录，指向同一物理文件）
        import secrets
        skipped_files: List[dict] = []
        for sfid in static_file_ids:
            src = await StaticFile.filter(id=sfid).first()
            if not src:
                continue

            # 源文件缺失时跳过，不创建无效记录
            if not os.path.exists(src.file_path):
                logger.warning(f"复制StaticFile id={sfid} 跳过：源文件不存在 {src.file_path}")
                skipped_files.append({"id": sfid, "name": src.name, "reason": "源文件已丢失"})
                continue

            new_token = secrets.token_hex(16)

            # 不拷贝物理文件，创建数据库记录指向同一文件（复制到工作区共享源文件）
            await StaticFile.create(
                workspace_id=target_workspace_id,
                name=src.name,
                description=src.description,
                file_name=src.file_name,
                file_path=src.file_path,  # 指向同一物理文件
                file_size=src.file_size,
                source_type=src.source_type,
                is_image=src.is_image,
                width=src.width,
                height=src.height,
                color_mode=src.color_mode,
                bit_depth=src.bit_depth,
                dpi=src.dpi,
                format_type=src.format_type,
                exif_data=src.exif_data,
                source=src.source,
                short_url_token=new_token,
            )
            copied["static_files"] += 1

        if skipped_files:
            copied["skipped"] = skipped_files

        return copied


class DatabaseImportService:
    """数据库数据导入服务：MySQL / SQLite / 像素平台 / 路网"""

    UPLOAD_DIR = os.path.join(settings.BASE_DIR, "uploads", "sheets")

    @classmethod
    def _ensure_dir(cls):
        os.makedirs(cls.UPLOAD_DIR, exist_ok=True)

    @classmethod
    def _save_csv(cls, df: pd.DataFrame, filename: str) -> tuple:
        """保存 DataFrame 为 CSV 文件，返回 (file_path, file_size, char_count, row_count)"""
        cls._ensure_dir()
        # 确保唯一文件名
        base, ext = os.path.splitext(filename)
        unique_id = uuid.uuid4().hex[:8]
        filename = f"{base}_{unique_id}.csv"
        filepath = os.path.join(cls.UPLOAD_DIR, filename)
        df.to_csv(filepath, index=False, encoding="utf-8-sig")
        file_size = os.path.getsize(filepath)
        row_count = len(df)
        # 计算字符数：把所有单元格转为字符串后统计
        char_count = sum(
            len(str(val)) if pd.notna(val) else 0
            for _, row in df.iterrows()
            for val in row
        )
        return filepath, file_size, char_count, row_count

    # ── MySQL ──

    @staticmethod
    def _mysql_get_connection(host: str, port: int, user: str, password: str, database: str):
        import pymysql
        return pymysql.connect(
            host=host, port=port, user=user, password=password,
            database=database, charset="utf8mb4",
            connect_timeout=10, read_timeout=60,
        )

    @classmethod
    def _mysql_list_tables_sync(cls, host: str, port: int, user: str, password: str, database: str) -> List[dict]:
        conn = cls._mysql_get_connection(host, port, user, password, database)
        try:
            with conn.cursor() as cursor:
                cursor.execute("SHOW TABLES")
                tables = [{"name": row[0], "label": row[0]} for row in cursor.fetchall()]
                # 获取每个表的行数估计和更新时间
                for t in tables:
                    try:
                        cursor.execute(
                            f"SELECT TABLE_ROWS, UPDATE_TIME FROM information_schema.TABLES "
                            f"WHERE TABLE_SCHEMA=%s AND TABLE_NAME=%s",
                            (database, t["name"]),
                        )
                        row = cursor.fetchone()
                        if row:
                            t["estimated_rows"] = row[0] or 0
                            t["update_time"] = str(row[1]) if row[1] else ""
                    except Exception:
                        t["estimated_rows"] = 0
                        t["update_time"] = ""
                return tables
        finally:
            conn.close()

    @classmethod
    def _mysql_import_table_sync(cls, host: str, port: int, user: str, password: str,
                                  database: str, table: str) -> str:
        """读取 MySQL 表数据并保存为 CSV，返回文件路径"""
        conn = cls._mysql_get_connection(host, port, user, password, database)
        try:
            query = f"SELECT * FROM `{table}`"
            # 获取原表更新时间
            update_time = None
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT UPDATE_TIME FROM information_schema.TABLES "
                    "WHERE TABLE_SCHEMA=%s AND TABLE_NAME=%s",
                    (database, table),
                )
                row = cursor.fetchone()
                if row and row[0]:
                    update_time = row[0]

            df = pd.read_sql(query, conn)
            filepath, file_size, char_count, row_count = cls._save_csv(df, f"{database}_{table}")
            return filepath, file_size, char_count, row_count, update_time
        finally:
            conn.close()

    @classmethod
    async def mysql_list_tables(cls, host: str, port: int, user: str, password: str, database: str) -> List[dict]:
        return await asyncio.to_thread(cls._mysql_list_tables_sync, host, port, user, password, database)

    @classmethod
    async def mysql_import_tables(
        cls, workspace_id: int, host: str, port: int, user: str,
        password: str, database: str, tables: List[str],
    ) -> List[dict]:
        """批量导入 MySQL 表数据"""
        from app.models.admin import Document
        results = []
        for table in tables:
            logger.info(f"导入 MySQL 表: {database}.{table}")
            filepath, file_size, char_count, row_count, update_time = await asyncio.to_thread(
                cls._mysql_import_table_sync, host, port, user, password, database, table
            )
            doc = await Document.create(
                workspace_id=workspace_id,
                name=f"{database}.{table}.csv",
                file_path=filepath,
                file_size=file_size,
                char_count=char_count,
                source_type="original",
                import_source="mysql",
                source_table=f"{database}.{table}",
                row_count=row_count,
                dump_date=datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None),
                source_last_updated=update_time,
            )
            results.append(await doc.to_dict())
        return results

    # ── SQLite ──

    @staticmethod
    def _sqlite_list_tables_sync(file_path: str) -> List[dict]:
        import sqlite3
        conn = sqlite3.connect(file_path)
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
            )
            tables = [{"name": row[0], "label": row[0]} for row in cursor.fetchall()]
            # 获取行数
            for t in tables:
                try:
                    cursor.execute(f'SELECT COUNT(*) FROM "{t["name"]}"')
                    t["estimated_rows"] = cursor.fetchone()[0]
                except Exception:
                    t["estimated_rows"] = 0
                t["update_time"] = ""
            return tables
        finally:
            conn.close()

    @classmethod
    def _sqlite_import_table_sync(cls, file_path: str, table: str) -> tuple:
        import sqlite3
        conn = sqlite3.connect(file_path)
        try:
            df = pd.read_sql_query(f'SELECT * FROM "{table}"', conn)
            base_name = os.path.basename(file_path).rsplit(".", 1)[0]
            filepath, file_size, char_count, row_count = cls._save_csv(df, f"{base_name}_{table}")
            return filepath, file_size, char_count, row_count
        finally:
            conn.close()

    @classmethod
    async def sqlite_list_tables(cls, file_path: str) -> List[dict]:
        return await asyncio.to_thread(cls._sqlite_list_tables_sync, file_path)

    @classmethod
    async def sqlite_import_tables(
        cls, workspace_id: int, file_path: str, tables: List[str],
    ) -> List[dict]:
        from app.models.admin import Document
        results = []
        base_name = os.path.basename(file_path)
        for table in tables:
            logger.info(f"导入 SQLite 表: {file_path} -> {table}")
            filepath, file_size, char_count, row_count = await asyncio.to_thread(
                cls._sqlite_import_table_sync, file_path, table
            )
            doc = await Document.create(
                workspace_id=workspace_id,
                name=f"{base_name}_{table}.csv",
                file_path=filepath,
                file_size=file_size,
                char_count=char_count,
                source_type="original",
                import_source="sqlite",
                source_table=table,
                row_count=row_count,
                dump_date=datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None),
            )
            results.append(await doc.to_dict())
        return results

    # ── 像素平台 ──

    @classmethod
    async def pixel_list_accounts(cls, user_id: int) -> List[dict]:
        """列出当前用户有权限访问的像素账户"""
        from app.models.admin import PixelAccount
        accounts = await PixelAccount.filter(users__id=user_id).all()
        return [
            {
                "id": a.id,
                "username": a.username,
                "tenant_address": a.tenant_address,
                "country": a.country,
                "state": a.state,
                "label": f"{a.username} ({a.tenant_address})",
            }
            for a in accounts
        ]

    @classmethod
    async def pixel_list_tables(cls, pixel_account_id: int, user_id: int) -> List[dict]:
        """列出像素平台数据表（缺陷表 / 轨迹表）"""
        from app.models.admin import PixelAccount
        acc = await PixelAccount.filter(id=pixel_account_id, users__id=user_id).first()
        if not acc:
            raise ValueError("无权访问该像素账户")
        # 像素平台当前支持两大数据表
        return [
            {"name": "defect", "label": "缺陷数据", "description": "路面病害检测数据"},
            {"name": "track", "label": "轨迹数据", "description": "车辆轨迹数据"},
        ]

    @classmethod
    async def pixel_import_table(
        cls, workspace_id: int, pixel_account_id: int, table_name: str, table_label: str, user_id: int,
    ) -> dict:
        """从本地数据库导入像素关联表的全量数据"""
        from app.models.admin import Defect, Document, PixelAccount, Track
        acc = await PixelAccount.filter(id=pixel_account_id, users__id=user_id).first()
        if not acc:
            raise ValueError("无权访问该像素账户")

        cls._ensure_dir()
        label = table_label or table_name

        if table_name == "defect":
            records = await Defect.filter(pixel_account_id=pixel_account_id).all()
            rows = [
                {
                    "remote_id": r.remote_id, "longitude": r.longitude, "latitude": r.latitude,
                    "status": r.status, "status_name": r.status_name,
                    "risk_type": r.risk_type, "risk_level": r.risk_level,
                    "risk_level_name": r.risk_level_name, "risk_name1": r.risk_name1,
                    "risk_name2": r.risk_name2, "lane": r.lane, "car_no": r.car_no,
                    "reverse_name": r.reverse_name, "subd_name": r.subd_name,
                    "track_image": r.track_image, "track_url": r.track_url,
                    "created_at": str(r.created_at) if r.created_at else "",
                }
                for r in records
            ]
        elif table_name == "track":
            records = await Track.filter(pixel_account_id=pixel_account_id).all()
            rows = [
                {
                    "remote_id": r.remote_id, "car_id": r.car_id, "road_name": r.road_name,
                    "car_type": r.car_type, "longitude": r.longitude, "latitude": r.latitude,
                    "flag": r.flag, "track_time": str(r.track_time) if r.track_time else "",
                    "created_at": str(r.created_at) if r.created_at else "",
                }
                for r in records
            ]
        else:
            raise ValueError(f"不支持的数据表: {table_name}")

        if not rows:
            raise ValueError(f"数据表 {label} 无数据")

        df = pd.DataFrame(rows)
        filepath, file_size, char_count, row_count = cls._save_csv(
            df, f"pixel_{acc.tenant_address}_{table_name}"
        )
        doc = await Document.create(
            workspace_id=workspace_id,
            name=f"pixel_{acc.tenant_address}_{table_name}.csv",
            file_path=filepath,
            file_size=file_size,
            char_count=char_count,
            source_type="original",
            import_source="pixel",
            source_table=f"{acc.tenant_address}.{table_name}",
            row_count=row_count,
            dump_date=datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None),
        )
        return await doc.to_dict()

    # ── 路网数据 ──

    @classmethod
    async def road_network_list_regions(cls) -> List[dict]:
        """列出有路网数据的区域树：含完整层级路径，前端可做面包屑导航"""
        from app.models.admin import Region, RoadNetwork
        from app.models.enums import RoadNetworkStatus

        # 找到所有有成功下载路网的区域
        networks = await RoadNetwork.filter(
            download_status=RoadNetworkStatus.SUCCESS, is_active=True
        ).select_related("region").all()

        # 收集区域集合
        region_map: dict = {}
        for nw in networks:
            r = nw.region
            if r.id not in region_map:
                region_map[r.id] = {
                    "id": r.id,
                    "name": r.name,
                    "local_name": r.local_name,
                    "code": r.code,
                    "region_type": str(r.region_type),
                    "parent_id": r.parent_id,
                    "network_count": 0,
                }
            region_map[r.id]["network_count"] += 1

        # 构建 parent 查找映射
        all_parents = set()
        for r in region_map.values():
            if r["parent_id"]:
                all_parents.add(r["parent_id"])
        # 补全父级区域信息
        if all_parents:
            parents = await Region.filter(id__in=list(all_parents)).all()
            for p in parents:
                if p.id not in region_map:
                    region_map[p.id] = {
                        "id": p.id,
                        "name": p.name,
                        "local_name": p.local_name,
                        "code": p.code,
                        "region_type": str(p.region_type),
                        "parent_id": p.parent_id,
                        "network_count": 0,
                    }

        # 构建完整路径
        sorted_regions = sorted(region_map.values(), key=lambda r: (r["region_type"], r["name"]))
        for r in sorted_regions:
            path_parts = []
            cursor = r
            while cursor:
                path_parts.insert(0, cursor["name"])
                pid = cursor["parent_id"]
                cursor = region_map.get(pid) if pid else None
            r["full_path"] = " > ".join(path_parts)
            r["label"] = f'{r["full_path"]} ({r["network_count"]} 路网)'

        return sorted_regions

    @classmethod
    async def road_network_list_for_region(cls, region_id: int) -> List[dict]:
        """列出某区域下的路网文件，含 stats 预览"""
        from app.models.admin import RoadNetwork
        from app.models.enums import RoadNetworkStatus
        networks = await RoadNetwork.filter(
            region_id=region_id,
            download_status=RoadNetworkStatus.SUCCESS,
            is_active=True,
        ).all()

        result = []
        for n in networks:
            item = {
                "id": n.id,
                "file_name": n.file_name,
                "file_type": n.file_type,
                "file_size": n.file_size,
                "node_count": n.node_count,
                "edge_count": n.edge_count,
                "srid": n.srid,
                "download_mode": n.download_mode,
                "created_at": str(n.created_at) if n.created_at else "",
                "label": (
                    f"{n.file_name} "
                    f"(节点:{n.node_count or 0} 边:{n.edge_count or 0}"
                ),
            }

            # 从 stats_json 提取预览数据
            if n.stats_json:
                try:
                    stats = json.loads(n.stats_json)
                    info = stats.get("info", {})
                    item["total_length_km"] = info.get("total_length_km")
                    item["density_km_per_km2"] = info.get("density_km_per_km2")
                    item["junction_count"] = info.get("junction_count")
                    highway_stats = info.get("highway_stats", [])
                    item["highway_count"] = len(highway_stats)
                    item["label"] += (
                        f" 总长:{info.get('total_length_km', '?')}km"
                        f" 密度:{info.get('density_km_per_km2', '?')}"
                    )
                except (json.JSONDecodeError, TypeError, KeyError):
                    pass
            item["label"] += ")"
            result.append(item)

        return result

    @classmethod
    async def road_network_import_stats(
        cls, workspace_id: int, region_id: int, road_network_ids: List[int],
    ) -> List[dict]:
        """将路网统计数据导入为 CSV 文档（每个路网产生汇总+明细两个 CSV）"""
        from app.models.admin import Document, Region, RoadNetwork
        results = []
        region = await Region.filter(id=region_id).first()
        region_name = region.name if region else "unknown"

        # 构建区域完整路径
        region_path = region_name
        if region and region.parent_id:
            parent = await Region.filter(id=region.parent_id).first()
            if parent:
                region_path = f"{parent.name} > {region_name}"
                if parent.parent_id:
                    grandparent = await Region.filter(id=parent.parent_id).first()
                    if grandparent:
                        region_path = f"{grandparent.name} > {parent.name} > {region_name}"

        for nw_id in road_network_ids:
            nw = await RoadNetwork.filter(id=nw_id).first()
            if not nw:
                continue

            # 读取 stats_json 获取详细统计
            stats = {}
            info = {}
            if nw.stats_json:
                try:
                    stats = json.loads(nw.stats_json)
                    info = stats.get("info", {})
                except (json.JSONDecodeError, TypeError):
                    pass

            safe_name = region_name.replace("/", "_").replace(" ", "_")
            base = f"路网_{safe_name}"

            # ── 1. 汇总 CSV：每个路网一行，含核心指标 ──
            summary_rows = [{
                "区域路径": region_path,
                "区域类型": str(region.region_type) if region else "",
                "文件名": nw.file_name,
                "文件类型": nw.file_type,
                "文件大小_字节": nw.file_size,
                "下载模式": nw.download_mode,
                "坐标系": nw.srid,
                "节点数": nw.node_count,
                "边数": nw.edge_count,
                "总里程_km": info.get("total_length_km", ""),
                "总里程_m": info.get("total_length_m", ""),
                "路网密度_km每km2": info.get("density_km_per_km2", ""),
                "路口数": info.get("junction_count", ""),
                "道路等级种类数": len(info.get("highway_stats", [])),
                "bbox_W": (info.get("bbox") or [None])[0],
                "bbox_S": (info.get("bbox") or [None, None])[1],
                "bbox_E": (info.get("bbox") or [None, None, None])[2],
                "bbox_N": (info.get("bbox") or [None, None, None, None])[3],
                "路网创建时间": str(nw.created_at) if nw.created_at else "",
                "数据导出时间": datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None).isoformat(),
            }]

            df_summary = pd.DataFrame(summary_rows)
            fpath_s, fsize_s, ccount_s, rcount_s = cls._save_csv(
                df_summary, f"{base}_{nw.file_name}_汇总"
            )
            doc_summary = await Document.create(
                workspace_id=workspace_id,
                name=f"{base}_{nw.file_name}_汇总.csv",
                file_path=fpath_s, file_size=fsize_s, char_count=ccount_s,
                source_type="original", import_source="road_network",
                source_table=f"region_{region_id}.road_network_{nw_id}.summary",
                row_count=rcount_s, dump_date=datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None),
                source_last_updated=nw.created_at,
            )
            results.append(await doc_summary.to_dict())

            # ── 2. 明细 CSV：每行一个道路等级，含中文名/边数/占比/里程 ──
            highway_stats = info.get("highway_stats", [])
            if highway_stats:
                detail_rows = []
                for hs in highway_stats:
                    # 尝试获取该等级的里程（如果 analyzer 存储了 length）
                    detail_rows.append({
                        "区域路径": region_path,
                        "文件名": nw.file_name,
                        "道路等级_code": hs.get("type", ""),
                        "道路等级_中文名": hs.get("name_zh", hs.get("type", "")),
                        "边数量": hs.get("count", 0),
                        "占比_pct": hs.get("percent", 0),
                        "累计长度_m": hs.get("length", ""),
                        "累计长度_km": round(hs.get("length", 0) / 1000, 2) if hs.get("length") else "",
                    })

                df_detail = pd.DataFrame(detail_rows)
                fpath_d, fsize_d, ccount_d, rcount_d = cls._save_csv(
                    df_detail, f"{base}_{nw.file_name}_道路等级明细"
                )
                doc_detail = await Document.create(
                    workspace_id=workspace_id,
                    name=f"{base}_{nw.file_name}_道路等级明细.csv",
                    file_path=fpath_d, file_size=fsize_d, char_count=ccount_d,
                    source_type="original", import_source="road_network",
                    source_table=f"region_{region_id}.road_network_{nw_id}.detail",
                    row_count=rcount_d, dump_date=datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None),
                    source_last_updated=nw.created_at,
                )
                results.append(await doc_detail.to_dict())

        return results


workspace_controller = WorkspaceController()
