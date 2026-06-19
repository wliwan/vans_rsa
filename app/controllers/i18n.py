"""国际化管理控制器

管理 web/i18n/messages/ 下的 JSON 翻译文件，提供读取、写入、导入导出、
AI 翻译生成、前端硬编码扫描等功能。
"""

import asyncio
import json
import logging
import os
import re
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from app.schemas.i18n import HardcodedString, I18nEntry

logger = logging.getLogger(__name__)

# i18n 消息文件目录（相对于项目根目录）
_MESSAGES_DIR = Path(__file__).resolve().parent.parent.parent / "web" / "i18n" / "messages"
_INDEX_JS = _MESSAGES_DIR / "index.js"

# 需要忽略的前端扫描目录/文件
_SCAN_EXCLUDE_DIRS = {
    "node_modules", "dist", "public", "lib", "__pycache__", ".git", "uploads",
    "cache", "i18n",  # i18n 目录本身就是翻译文件
}
_SCAN_EXCLUDE_FILES = {
    "pnpm-lock.yaml", "package-lock.json", "yarn.lock",
}
_SCAN_INCLUDE_EXTS = {".vue", ".js", ".ts", ".jsx", ".tsx"}


def _get_project_root() -> Path:
    """获取项目根目录"""
    return Path(__file__).resolve().parent.parent.parent


class I18nController:
    """国际化控制器（非 CRUDBase，直接操作 JSON 文件）"""

    # ─── 文件读写 ───────────────────────────────────────────────

    def _get_locale_path(self, locale: str) -> Path:
        """获取 locale 对应的 JSON 文件路径"""
        return _MESSAGES_DIR / f"{locale}.json"

    def _get_locales(self) -> List[str]:
        """获取所有可用语言列表"""
        locales = []
        if not _MESSAGES_DIR.exists():
            return locales
        for f in sorted(_MESSAGES_DIR.glob("*.json")):
            locales.append(f.stem)
        return locales

    def _load_locale(self, locale: str) -> Dict[str, Any]:
        """加载单个语言文件"""
        filepath = self._get_locale_path(locale)
        if not filepath.exists():
            return {}
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)

    def _save_locale(self, locale: str, data: Dict[str, Any]):
        """保存单个语言文件（自动备份）"""
        filepath = self._get_locale_path(locale)
        filepath.parent.mkdir(parents=True, exist_ok=True)

        # 写入临时文件后原子 rename
        tmp = filepath.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.write("\n")
        os.replace(tmp, filepath)

    # ─── 扁平化 / 还原 ──────────────────────────────────────────

    def _flatten(
        self, obj: Any, prefix: str = ""
    ) -> List[Tuple[str, Any, str]]:
        """将嵌套 JSON 扁平化为 (key, value, type) 列表，key 用 . 分隔"""
        result = []
        if isinstance(obj, dict):
            # 注意：需要保留数组类型的叶子值（如 typeOptions 的值是 list）
            for k, v in obj.items():
                full_key = f"{prefix}.{k}" if prefix else k

                if isinstance(v, dict):
                    result.extend(self._flatten(v, full_key))
                elif isinstance(v, list):
                    # 检查列表元素是否全是对象（如 typeOptions 是一个列表）
                    if v and all(isinstance(item, dict) for item in v):
                        # 对象数组，保留原样
                        result.append((full_key, v, "array"))
                    else:
                        result.append((full_key, v, "array"))
                else:
                    type_str = "string"
                    if isinstance(v, bool):
                        type_str = "boolean"
                    elif isinstance(v, (int, float)):
                        type_str = "number"
                    result.append((full_key, v, type_str))
        return result

    def _unflatten(self, flat_list: List[Tuple[str, Any]]) -> Dict[str, Any]:
        """将扁平化列表还原为嵌套 JSON"""
        result = {}
        for key, value in flat_list:
            parts = key.split(".")
            current = result
            for i, part in enumerate(parts[:-1]):
                if part not in current:
                    current[part] = {}
                if not isinstance(current[part], dict):
                    # 冲突：叶子值被变成了中间节点，跳过
                    break
                current = current[part]
            else:
                current[parts[-1]] = value
        return result

    # ─── 业务方法 ───────────────────────────────────────────────

    async def get_all(self) -> Dict[str, Any]:
        """获取所有语言的完整数据（用于导出）"""
        result = {}
        for locale in self._get_locales():
            result[locale] = self._load_locale(locale)
        return result

    async def get_list(self) -> Dict[str, Any]:
        """获取国际化列表（表格展示用）

        返回格式: { "locales": [...], "entries": [{key, type, translations}] }
        """
        locales = self._get_locales()
        if not locales:
            return {"locales": [], "entries": []}

        # 加载所有语言
        locale_data = {}
        for loc in locales:
            locale_data[loc] = self._load_locale(loc)

        # 以 cn（或第一个语言）为基准收集所有 key
        primary_locale = "cn" if "cn" in locales else locales[0]
        primary_data = locale_data.get(primary_locale, {})

        flat_keys = self._flatten(primary_data)

        entries = []
        for key, _, key_type in flat_keys:
            translations = {}
            for loc in locales:
                val = self._get_value_by_key(locale_data.get(loc, {}), key)
                translations[loc] = val
            entries.append(
                {
                    "key": key,
                    "type": key_type,
                    "translations": translations,
                }
            )

        return {"locales": locales, "entries": entries}

    def _get_value_by_key(self, data: Dict, key: str) -> Any:
        """根据点分隔的 key 获取嵌套字典中的值"""
        parts = key.split(".")
        current = data
        for part in parts:
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return None
        return current

    async def update(self, key: str, locale: str, value: Any) -> bool:
        """更新单个翻译条目"""
        filepath = self._get_locale_path(locale)
        if not filepath.exists():
            return False

        data = self._load_locale(locale)
        if not await self._set_value_by_key(data, key, value):
            return False

        self._save_locale(locale, data)
        return True

    async def _set_value_by_key(
        self, data: Dict, key: str, value: Any
    ) -> bool:
        """根据点分隔的 key 设置嵌套字典中的值，自动创建缺失的中间节点"""
        parts = key.split(".")
        current = data
        for part in parts[:-1]:
            if part not in current:
                current[part] = {}
            if not isinstance(current[part], dict):
                return False
            current = current[part]
        current[parts[-1]] = value
        return True

    async def batch_update(
        self, updates: List[Tuple[str, str, Any]]
    ) -> int:
        """批量更新翻译，返回成功数"""
        success = 0
        for key, locale, value in updates:
            if await self.update(key, locale, value):
                success += 1
        return success

    async def export_data(self) -> Dict[str, Any]:
        """导出所有语言数据"""
        return await self.get_all()

    async def import_data(self, locale: str, data: Dict[str, Any]) -> bool:
        """导入单个语言的翻译数据"""
        self._save_locale(locale, data)
        # 同时更新 index.js
        await self._sync_index_js()
        return True

    async def _sync_index_js(self):
        """同步更新 web/i18n/messages/index.js（导入语句）"""
        locales = self._get_locales()
        lines = []
        for loc in locales:
            lines.append(f"import {loc} from './{loc}.json'")
        lines.append("")
        lines.append("export default {")
        for loc in locales:
            lines.append(f"  {loc},")
        lines.append("}")
        lines.append("")
        with open(_INDEX_JS, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

    # ─── AI 翻译生成 ───────────────────────────────────────────

    async def ai_generate(
        self,
        ai_proxy_name: str,
        target_locale: str,
        target_lang_name: str,
        prompt_extra: Optional[str] = None,
    ) -> Dict[str, Any]:
        """使用 AI 代理生成新语言翻译

        流程：
        1. 获取 cn.json 作为源数据
        2. 调用 AI 代理 API 翻译所有文本
        3. 解析 AI 返回的 JSON
        4. 保存到目标语言文件
        5. 更新 index.js
        """
        import httpx

        from app.controllers.ai_proxy import ai_proxy_controller

        # 1. 获取 AI 代理
        proxy = await ai_proxy_controller.get_by_name(ai_proxy_name)
        if not proxy:
            raise ValueError(f"AI 代理 '{ai_proxy_name}' 不存在")

        # 2. 获取 cn.json 作为源，只提取字符串类型的叶子值
        cn_data = self._load_locale("cn")
        flat_cn = self._flatten(cn_data)

        # 只翻译 string 类型的字段
        string_entries = [
            (key, value) for key, value, typ in flat_cn if typ == "string"
        ]

        # 构建 AI 提示词
        batch_size = 50
        translated = {}

        for i in range(0, len(string_entries), batch_size):
            batch = string_entries[i : i + batch_size]
            batch_dict = {key: value for key, value in batch}

            system_prompt = (
                f"你是一个专业翻译助手。请将以下中文翻译成{target_lang_name}。\n"
                "要求：\n"
                "1. 保留 {variable} 形式的变量占位符不翻译\n"
                "2. 保留 HTML 标签和特殊字符\n"
                "3. 翻译要自然流畅，符合目标语言习惯\n"
                "4. 只返回 JSON 对象，key 为字段路径，value 为翻译文本\n"
                "5. 不要添加任何解释或额外文本"
            )
            if prompt_extra:
                system_prompt += f"\n额外要求：{prompt_extra}"

            user_prompt = f"请翻译以下 JSON 中的值（只翻译 value，key 保持不变）：\n{json.dumps(batch_dict, ensure_ascii=False, indent=2)}"

            try:
                result = await self._call_ai(proxy, system_prompt, user_prompt)
                # 解析 AI 返回的 JSON
                batch_translated = self._extract_json(result)
                if isinstance(batch_translated, dict):
                    translated.update(batch_translated)
            except Exception as e:
                logger.error(f"AI 翻译批次 {i} 失败: {e}")
                raise

        # 4. 构建目标语言完整数据（深拷贝 cn 结构，替换字符串值）
        target_data = await self._build_translated_data(cn_data, translated)

        # 5. 保存
        self._save_locale(target_locale, target_data)
        await self._sync_index_js()

        return {
            "locale": target_locale,
            "translated_count": len(translated),
            "total_count": len(string_entries),
        }

    async def _call_ai(
        self, proxy, system_prompt: str, user_prompt: str
    ) -> str:
        """调用 AI 代理 API"""
        import httpx

        url = proxy.url.rstrip("/") + "/chat/completions"
        headers = {
            "Authorization": f"Bearer {proxy.token}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": proxy.model or "gpt-4",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.3,
        }

        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"]

    def _extract_json(self, text: str) -> Any:
        """从 AI 回复中提取 JSON"""
        # 尝试直接解析
        text = text.strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # 尝试提取 ```json ... ``` 块
        m = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(1))
            except json.JSONDecodeError:
                pass

        # 尝试提取 { ... } 块
        m = re.search(r"\{.*\}", text, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(0))
            except json.JSONDecodeError:
                pass

        raise ValueError(f"无法从 AI 回复中解析 JSON: {text[:500]}")

    async def _build_translated_data(
        self, cn_data: Dict, translations: Dict[str, str]
    ) -> Dict:
        """基于 cn 结构，用翻译结果构建目标语言数据结构"""
        result = deepcopy(cn_data)

        def _replace(obj, prefix=""):
            if isinstance(obj, dict):
                for k, v in obj.items():
                    full_key = f"{prefix}.{k}" if prefix else k
                    if isinstance(v, str):
                        if full_key in translations:
                            obj[k] = translations[full_key]
                    elif isinstance(v, dict):
                        _replace(v, full_key)
                    elif isinstance(v, list):
                        # 列表不递归翻译（如 typeOptions 已经是对象数组）
                        pass

        _replace(result)
        return result

    # ─── 前端硬编码扫描 ─────────────────────────────────────────

    async def scan_frontend(self) -> Dict[str, Any]:
        """扫描前端代码中的硬编码中文字符串

        扫描 web/src/ 下所有 .vue/.js/.ts 文件，查找未使用 $t()/t() 的中文硬编码。
        """
        project_root = _get_project_root()
        src_dir = project_root / "web" / "src"

        results = []
        # 中文正则：匹配中文字符、中文标点
        chinese_pattern = re.compile(r"[\u4e00-\u9fff\u3000-\u303f\uff00-\uffef]+")

        # 已存在的 i18n key 用于排除
        existing_keys = set()
        for loc in self._get_locales():
            data = self._load_locale(loc)
            for key, value, _ in self._flatten(data):
                if isinstance(value, str) and value.strip():
                    existing_keys.add(value)

        for filepath in src_dir.rglob("*"):
            if not filepath.is_file():
                continue

            # 排除目录
            parts = filepath.relative_to(src_dir).parts
            if any(p in _SCAN_EXCLUDE_DIRS for p in parts):
                continue
            if filepath.suffix not in _SCAN_INCLUDE_EXTS:
                continue
            if filepath.name in _SCAN_EXCLUDE_FILES:
                continue

            try:
                content = filepath.read_text(encoding="utf-8")
            except Exception:
                continue

            lines = content.split("\n")
            for line_no, line in enumerate(lines, 1):
                # 跳过注释行
                stripped = line.strip()
                if stripped.startswith("//") or stripped.startswith("#"):
                    continue
                if stripped.startswith("/*") or stripped.startswith("*"):
                    continue

                # 跳过包含 $t( 或 t( 或 useI18n 的行
                if "$t(" in line or " t(" in line or "t(" in line or "useI18n" in line:
                    continue

                # 查找中文字符串
                matches = re.findall(r"""[“"'`]([^"'`]*[\u4e00-\u9fff][^"'`]*)["'`]""", line)
                for match in matches:
                    # 过滤已存在的翻译值
                    if match in existing_keys:
                        continue
                    # 过滤纯数字/英文字符
                    chinese_chars = chinese_pattern.findall(match)
                    if not chinese_chars:
                        continue
                    suggested_key = self._suggest_key(match, filepath)
                    results.append(
                        {
                            "file": str(filepath.relative_to(src_dir)),
                            "line": line_no,
                            "text": match,
                            "context": line.strip()[:200],
                            "suggested_key": suggested_key,
                        }
                    )

        return {"total": len(results), "items": results}

    async def replace_hardcoded(
        self, items: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """批量替换硬编码字符串为 i18n 调用"""
        project_root = _get_project_root()
        src_dir = project_root / "web" / "src"
        success_count = 0
        errors = []

        for item in items:
            file_path = src_dir / item["file"]
            if not file_path.exists():
                errors.append(f"文件不存在: {item['file']}")
                continue

            try:
                content = file_path.read_text(encoding="utf-8")
                lines = content.split("\n")
                line_idx = item["line"] - 1
                if line_idx < 0 or line_idx >= len(lines):
                    errors.append(f"行号超范围: {item['file']}:{item['line']}")
                    continue

                old_line = lines[line_idx]
                new_line = item.get("replacement", old_line)
                lines[line_idx] = new_line
                file_path.write_text("\n".join(lines), encoding="utf-8")
                success_count += 1
            except Exception as e:
                errors.append(f"替换失败 {item['file']}:{item['line']}: {e}")

        return {"success": success_count, "errors": errors}

    def _suggest_key(self, text: str, filepath: Path) -> str:
        """根据文本内容和文件路径建议 i18n key"""
        # 简化文本作为 key 的一部分
        short = text[:20].strip()
        # 根据文件路径推断模块名
        parts = filepath.parts
        module = "common"
        for part in parts:
            if part in ("views", "components", "layout"):
                idx = list(parts).index(part)
                if idx + 1 < len(parts):
                    module = parts[idx + 1]
                break
        # 生成 key
        key_part = re.sub(r"[^\w]", "_", short).strip("_").lower()
        if not key_part:
            key_part = "text"
        return f"views.{module}.{key_part}"


# 单例
i18n_controller = I18nController()
