"""国际化管理控制器

管理 web/i18n/messages/ 下的 JSON 翻译文件，提供读取、写入、导入导出、
AI 翻译、前端硬编码扫描等功能。
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

    # ─── AI 翻译 ───────────────────────────────────────────────

    # locale → 语言中文名映射（用于 AI 提示词）
    _LANG_NAME_MAP: Dict[str, str] = {
        "en": "英文",
        "jp": "日文",
        "fr": "法文",
        "de": "德文",
        "ko": "韩文",
        "es": "西班牙文",
        "ru": "俄文",
        "ar": "阿拉伯文",
        "pt": "葡萄牙文",
        "it": "意大利文",
        "th": "泰文",
        "vi": "越南文",
        "tr": "土耳其文",
        "nl": "荷兰文",
        "pl": "波兰文",
        "sv": "瑞典文",
        "da": "丹麦文",
        "fi": "芬兰文",
        "el": "希腊文",
        "he": "希伯来文",
        "id": "印尼文",
    }
    # 每批翻译的最大条目数（根据 AI token 限制留 30% 冗余）
    _BATCH_SIZE: int = 50
    # 并行批次上限（避免同时发出过多请求）
    _MAX_CONCURRENT_BATCHES: int = 10

    def _build_translate_system_prompt(
        self, target_lang_name: str, mode: str
    ) -> str:
        """构建翻译 system prompt，确保翻译质量与系统契合"""
        mode_hint = ""
        if mode == "incremental":
            mode_hint = (
                "注意：这是一批**增量补充**的条目，它们来自一个已有的后台管理系统翻译文件，"
                "请确保新翻译的风格与已有翻译保持一致。\n"
            )

        return (
            f"{mode_hint}"
            f"你是一位专业的 UI 本地化翻译专家。请将以下中文翻译成{target_lang_name}。\n"
            "\n"
            "## 背景\n"
            "这些文本来自 vue-fastapi-admin，一个基于 Vue 3 + Naive UI 的企业后台管理系统。\n"
            "翻译需要符合后台管理系统的 UI 风格：简洁、专业、一致。\n"
            "\n"
            "## 翻译规范\n"
            "1. **占位符**：保留 {name}、{count}、{0} 等花括号/模板变量，不要翻译变量名\n"
            "2. **HTML 标签**：保留 <br>、<b>、<i>、&nbsp;、&lt;、&gt; 等，不要转义或删除\n"
            "3. **简洁原则**：后台 UI 空间有限，翻译应尽量简短。中文四字格可简化为英文 1-2 词\n"
            "   例如：「确认删除」→「Delete」（而非「Confirm Deletion」）\n"
            "   例如：「保存成功」→「Saved」（而非「Save Successful」）\n"
            "4. **术语一致性**：常见 UI 术语保持统一翻译\n"
            "   - 确定/确认 → OK / Confirm（根据语境，操作确认用 OK，内容确认用 Confirm）\n"
            "   - 取消 → Cancel\n"
            "   - 新增/添加 → Add\n"
            "   - 编辑/修改 → Edit\n"
            "   - 删除 → Delete\n"
            "   - 查看 → View\n"
            "   - 搜索/查询 → Search\n"
            "   - 重置 → Reset\n"
            "   - 保存 → Save\n"
            "   - 提交 → Submit\n"
            "   - 导出 → Export\n"
            "   - 导入 → Import\n"
            "   - 刷新 → Refresh\n"
            "   - 上传 → Upload\n"
            "   - 下载 → Download\n"
            "   - 启用/禁用 → Enable / Disable\n"
            "   - 成功/失败 → Success / Failed\n"
            "   - 页码/分页 → Page / Pagination\n"
            "5. **自然流畅**：翻译应符合目标语言的表达习惯，避免生硬直译\n"
            "6. **特殊符号**：保留标点符号的语义，但可根据目标语言习惯调整（如中文顿号→英文逗号）\n"
            "\n"
            "## 输出格式\n"
            "只返回一个 JSON 对象，key 为字段路径（保持不变），value 为翻译后的文本。\n"
            "不要添加任何解释、注释或 Markdown 代码块标记。\n"
            "不要修改 key 的名称。"
        )

    async def ai_generate(
        self,
        ai_proxy_name: str,
        target_locale: str,
        mode: str = "full",
    ) -> Dict[str, Any]:
        """使用 AI 代理将中文翻译为目标语言

        两种模式：
        - full: 全量翻译，cn.json 中所有字符串条目全部重新翻译并替换
        - incremental: 增量翻译，只翻译目标语言中缺失或为空的条目，已有翻译保留

        流程：
        1. 读取 cn.json 作为源数据，确定待翻译条目
        2. 增量模式下对比目标语言文件，过滤已翻译条目
        3. 按 token 限制分片（每批 50 条，留 30% 冗余）
        4. 并行调用 AI 翻译所有分片
        5. 合并结果（增量模式：合并到现有数据；全量模式：基于 cn 结构重建）
        6. 保存并更新 index.js
        """
        from app.controllers.ai_proxy import ai_proxy_controller

        # 验证 mode
        if mode not in ("full", "incremental"):
            raise ValueError(f"不支持的翻译模式 '{mode}'，请使用 full 或 incremental")

        # 验证目标语言
        target_lang_name = self._LANG_NAME_MAP.get(target_locale)
        if not target_lang_name:
            raise ValueError(
                f"不支持的目标语言代码 '{target_locale}'，"
                f"支持的语言: {', '.join(sorted(self._LANG_NAME_MAP.keys()))}"
            )

        # 1. 获取 AI 代理
        proxy = await ai_proxy_controller.get_by_name(ai_proxy_name)
        if not proxy:
            raise ValueError(f"AI 代理 '{ai_proxy_name}' 不存在")

        # 2. 读取 cn.json，提取字符串类型的叶子值
        cn_data = self._load_locale("cn")
        flat_cn = self._flatten(cn_data)
        all_string_entries = [
            (key, value) for key, value, typ in flat_cn if typ == "string"
        ]

        # 3. 增量模式：对比目标语言文件，过滤已翻译条目
        existing_translations: dict = {}
        existing_data: dict = {}
        if mode == "incremental":
            existing_data = self._load_locale(target_locale)
            if existing_data:
                flat_existing = self._flatten(existing_data)
                # 构建已有翻译映射（key → value），值为非空字符串才算已翻译
                for key, value, _typ in flat_existing:
                    if isinstance(value, str) and value.strip():
                        existing_translations[key] = value
                # 过滤出未翻译的条目
                string_entries = [
                    (k, v) for k, v in all_string_entries
                    if k not in existing_translations
                ]
            else:
                # 目标文件不存在，增量模式退化为全量
                string_entries = list(all_string_entries)
        else:
            string_entries = list(all_string_entries)

        # 如果没有需要翻译的条目，直接返回
        if not string_entries:
            return {
                "locale": target_locale,
                "mode": mode,
                "translated_count": 0,
                "total_count": len(all_string_entries),
                "skipped_count": len(all_string_entries),
                "batch_count": 0,
                "failed_batches": None,
            }

        # 4. 分片
        batch_size = self._BATCH_SIZE
        batches: list = []
        for i in range(0, len(string_entries), batch_size):
            batch = string_entries[i : i + batch_size]
            batches.append({key: value for key, value in batch})

        # 5. 构建优化后的 system prompt
        system_prompt = self._build_translate_system_prompt(
            target_lang_name, mode
        )

        # 6. 并行调用 AI 翻译（限制并发数）
        sem = asyncio.Semaphore(self._MAX_CONCURRENT_BATCHES)

        async def _translate_batch(idx: int, batch_dict: dict) -> Tuple[int, dict, str | None]:
            """翻译单个批次，返回 (批次索引, 翻译结果, 错误信息)"""
            async with sem:
                user_prompt = (
                    "请翻译以下 JSON 中的值（只翻译 value，key 保持不变）：\n"
                    f"{json.dumps(batch_dict, ensure_ascii=False, indent=2)}"
                )
                try:
                    result = await self._call_ai(proxy, system_prompt, user_prompt)
                    batch_translated = self._extract_json(result)
                    if isinstance(batch_translated, dict):
                        return (idx, batch_translated, None)
                    else:
                        return (idx, {}, f"批次 {idx} 返回非字典类型: {type(batch_translated)}")
                except Exception as e:
                    logger.error(f"AI 翻译批次 {idx}（{len(batch_dict)} 条）失败: {e}")
                    return (idx, {}, str(e))

        tasks = [_translate_batch(i, batch_dict) for i, batch_dict in enumerate(batches)]
        results = await asyncio.gather(*tasks)

        # 7. 合并结果
        translated: dict = {}
        failed_batches: list = []
        for idx, batch_result, error in results:
            if error:
                failed_batches.append({"batch": idx, "count": len(batches[idx]), "error": error})
            else:
                translated.update(batch_result)

        # 8. 根据模式构建最终数据
        if mode == "incremental" and existing_data:
            # 增量模式：基于现有数据，替换/补充已翻译的值
            target_data = self._merge_incremental(
                existing_data, cn_data, existing_translations, translated
            )
        else:
            # 全量模式：基于 cn 结构，用翻译结果重建
            target_data = self._build_translated_data_sync(cn_data, translated)

        # 9. 保存
        self._save_locale(target_locale, target_data)
        await self._sync_index_js()

        return {
            "locale": target_locale,
            "mode": mode,
            "translated_count": len(translated),
            "total_count": len(all_string_entries),
            "skipped_count": len(existing_translations) if mode == "incremental" else 0,
            "batch_count": len(batches),
            "failed_batches": failed_batches if failed_batches else None,
        }

    def _merge_incremental(
        self,
        existing_data: dict,
        cn_data: dict,
        existing_translations: dict,
        new_translations: dict,
    ) -> dict:
        """增量合并：保留已有翻译，用新翻译补充缺失条目

        策略：基于 cn.json 的结构递归遍历，优先使用已有翻译，
              已有翻译不存在时使用新翻译，新翻译也不存在时保留 cn 原值（未翻译状态）。
        """
        result = deepcopy(existing_data)

        def _merge(obj, cn_obj, prefix=""):
            if not isinstance(obj, dict) or not isinstance(cn_obj, dict):
                return
            for k, cn_v in cn_obj.items():
                full_key = f"{prefix}.{k}" if prefix else k
                if isinstance(cn_v, dict):
                    # 嵌套对象：确保目标中存在，递归进入
                    if k not in obj or not isinstance(obj.get(k), dict):
                        obj[k] = deepcopy(cn_v)
                    _merge(obj[k], cn_v, full_key)
                elif isinstance(cn_v, str):
                    # 字符串叶子值：优先已有翻译，其次新翻译
                    if full_key in existing_translations:
                        # 已有翻译，保持不变（obj 中已有该值）
                        pass
                    elif full_key in new_translations:
                        # 新翻译，写入
                        obj[k] = new_translations[full_key]
                    elif k not in obj:
                        # 完全缺失，保留 cn 原值（后续可再次翻译）
                        obj[k] = cn_v
                elif isinstance(cn_v, list):
                    # 数组类型：如果目标中不存在，拷贝 cn 的结构
                    if k not in obj:
                        obj[k] = deepcopy(cn_v)

        _merge(result, cn_data)
        return result

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

    def _build_translated_data_sync(
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

    # ─── 扫描新字段并添加 ────────────────────────────────────────
    def _scan_chinese_texts(self) -> List[dict]:
        """扫描前端代码中所有直接使用中文的 UI 元素

        返回 [{"text":..., "file":..., "line":..., "prefix":...}, ...]
        """
        project_root = _get_project_root()
        src_dir = project_root / "web" / "src"
        results = []
        chinese_re = re.compile(r"[\u4e00-\u9fff\u3000-\u303f\uff00-\uffef]+")

        existing_texts = set()
        for loc in self._get_locales():
            data = self._load_locale(loc)
            for _k, v, _t in self._flatten(data):
                if isinstance(v, str) and v.strip():
                    existing_texts.add(v)

        for filepath in sorted(src_dir.rglob("*")):
            if not filepath.is_file():
                continue
            parts = tuple(filepath.relative_to(src_dir).parts)
            if any(p in _SCAN_EXCLUDE_DIRS for p in parts):
                continue
            if filepath.suffix not in _SCAN_INCLUDE_EXTS:
                continue
            try:
                content = filepath.read_text(encoding="utf-8")
            except Exception:
                continue

            prefix = self._derive_prefix(parts)
            rel_path = str(filepath.relative_to(src_dir))

            # —— 逐行扫描（引号字符串 + 模板字符串）——
            seen_in_file = {(r["text"], r["file"]) for r in results if r["file"] == rel_path}

            for line_no, line in enumerate(content.split("\n"), 1):
                # 跳过注释行
                stripped = line.strip()
                if stripped.startswith(("//", "#", "/*", "*")):
                    continue
                if not chinese_re.search(line):
                    continue

                # 预处理：剥离 t()/$t() 调用，避免整行跳过
                cleaned = self._strip_i18n_calls(line)
                texts = self._extract_chinese_strings(cleaned, chinese_re)
                for text in texts:
                    if text in existing_texts:
                        continue
                    if (text, rel_path) in seen_in_file:
                        continue
                    seen_in_file.add((text, rel_path))
                    results.append({"file": rel_path, "line": line_no, "text": text, "prefix": prefix})

            # —— 跨行 HTML 文本内容扫描（>中文< 可能跨行）——
            # 用 DOTALL 匹配跨越多行的 HTML 文本节点
            for m in re.finditer(r">\s*([^<]*[\u4e00-\u9fff][^<]*)<", content, re.DOTALL):
                t = m.group(1).strip()
                # 清理换行和多余空白
                t = re.sub(r"\s+", "", t)
                if not chinese_re.search(t) or len(t) < 1:
                    continue
                if t in existing_texts:
                    continue
                if (t, rel_path) in seen_in_file:
                    continue
                seen_in_file.add((t, rel_path))
                # 估算行号：数换行符到匹配位置
                approx_line = content[:m.start()].count("\n") + 1
                results.append({"file": rel_path, "line": approx_line, "text": t, "prefix": prefix})
        return results

    def _extract_chinese_strings(self, line: str, chinese_re) -> List[str]:
        """提取一行代码中含中文的字符串字面量（引号 + 模板字符串 + HTML 文本内容）"""
        texts = []
        # 先剥离 {{ }} Vue 模板表达式（避免误提取）
        no_mustache = re.sub(r"\{\{[^}]*\}\}", " ", line)

        # 模式1：单/双引号包裹的字符串
        for m in re.finditer(r"""(["'])((?:(?!\1).)*?[\u4e00-\u9fff](?:(?!\1).)*?)\1""", no_mustache):
            t = m.group(2).strip()
            if chinese_re.search(t) and len(t) >= 1:
                texts.append(t)
        for m in re.finditer(r"`([^`]*[\u4e00-\u9fff][^`]*)`", line):
            raw = m.group(1)
            if not chinese_re.search(raw):
                continue
            # 将 ${expr} 替换为 {0}, {1}... 占位符，保留结构含义
            _cnt = [0]
            def _repl(_m):
                _cnt[0] += 1
                return "{%d}" % (_cnt[0] - 1)
            normalized = re.sub(r"\$\{[^}]*\}", _repl, raw)
            normalized = normalized.strip()
            if chinese_re.search(normalized) and len(normalized) >= 1:
                texts.append(normalized)

        # 模式3：HTML 文本内容 >中文< （模板中未加引号的 UI 文本）
        for m in re.finditer(r">\s*([^<]*[\u4e00-\u9fff][^<]*)<", no_mustache):
            t = m.group(1).strip()
            # 清理嵌套的 HTML 标签残留（如 >中文</span> 已经由 < 边界处理）
            # 过滤纯数字/符号
            if not chinese_re.search(t):
                continue
            # 去掉可能残留的 {{ }} 片段
            t = re.sub(r"\{\{[^}]*\}\}", "", t).strip()
            if chinese_re.search(t) and len(t) >= 2:
                texts.append(t)
        return texts

    def _derive_prefix(self, parts: tuple) -> str:
        """从文件路径推导 key 前缀"""
        prefix_parts = []
        started = False
        for p in parts:
            if p.endswith((".vue", ".js", ".ts", ".jsx", ".tsx")):
                name = p.rsplit(".", 1)[0]
                name = re.sub(r"([A-Z])", r"_\1", name).lower().strip("_")
                name = re.sub(r"[^a-z0-9_]", "_", name)
                if name and name != "index":
                    prefix_parts.append(name)
                started = True
            elif started or p in ("views", "components", "layout"):
                prefix_parts.append(p)
                started = True
        return ".".join(prefix_parts) if prefix_parts else "common"

    def _strip_i18n_calls(self, line: str) -> str:
        """剥离行内的 t('...') / $t('...') 调用，替换为空格，保留其余文本"""
        # 匹配 t('...') 或 t("...")
        line = re.sub(r"\bt\s*\(\s*'[^']*'\s*\)", " ", line)
        line = re.sub(r'\bt\s*\(\s*"[^"]*"\s*\)', " ", line)
        # 匹配 $t('...') 或 $t("...")
        line = re.sub(r"\$t\s*\(\s*'[^']*'\s*\)", " ", line)
        line = re.sub(r'\$t\s*\(\s*"[^"]*"\s*\)', " ", line)
        return line


    # ─── AI 扫描添加 ────────────────────────────────────────────

    _SCAN_BATCH_SIZE: int = 30
    _SCAN_MAX_CONCURRENT: int = 8

    def _build_scan_add_system_prompt(self) -> str:
        return (
            "你是一位专业的前端国际化工程师。为一批中文 UI 文本生成 i18n key。\n"
            "\n"
            "## 背景\n"
            "vue-fastapi-admin，Vue 3 + Naive UI 企业后台管理系统。\n"
            "i18n 文件为嵌套 JSON（如 cn.json），key 用 . 分隔。\n"
            "\n"
            "## key 命名规范\n"
            "1. 点号 . 分隔层级，全 snake_case 小写\n"
            "2. 第一层：views / components / layout / common\n"
            "3. 第二层：模块/组件名\n"
            "4. 第三层+：语义化功能描述\n"
            "5. 简短中文（≤4字）key 用英文译词：确定→confirm，取消→cancel\n"
            "6. 较长文本 key 描述用途：确认删除该用户吗？→ confirm_delete_user\n"
            "7. 同一模块避冲突，必要时加后缀\n"
            "8. 优先使用给出的 prefix\n"
            "\n"
            "## 输入\n"
            "JSON 数组，每项: {text, prefix, file}\n"
            "\n"
            "## 输出\n"
            "仅返回 JSON 对象: {key: 原始text}。不解释，不改 value。"
        )

    async def scan_and_add(self, ai_proxy_name: str) -> Dict[str, Any]:
        """扫描前端硬编码中文 → AI 生成 key → 追加到 cn.json"""
        from app.controllers.ai_proxy import ai_proxy_controller
        proxy = await ai_proxy_controller.get_by_name(ai_proxy_name)
        if not proxy:
            raise ValueError(f"AI 代理 '{ai_proxy_name}' 不存在")

        raw_items = self._scan_chinese_texts()
        if not raw_items:
            return {"scanned_count": 0, "added_count": 0, "skipped_count": 0, "batch_count": 0, "failed_batches": None}

        batches = [raw_items[i:i + self._SCAN_BATCH_SIZE] for i in range(0, len(raw_items), self._SCAN_BATCH_SIZE)]
        sys_prompt = self._build_scan_add_system_prompt()
        sem = asyncio.Semaphore(self._SCAN_MAX_CONCURRENT)

        async def _proc(idx: int, batch: list) -> Tuple[int, dict, str | None]:
            async with sem:
                inp = [{"text": it["text"], "prefix": it["prefix"], "file": it["file"]} for it in batch]
                user = f"请为以下中文 UI 文本生成合适的 i18n key：\n{json.dumps(inp, ensure_ascii=False, indent=2)}"
                try:
                    r = await self._call_ai(proxy, sys_prompt, user)
                    p = self._extract_json(r)
                    return (idx, p if isinstance(p, dict) else {}, None if isinstance(p, dict) else f"批次 {idx} 非字典")
                except Exception as e:
                    logger.error(f"扫描添加批次 {idx} 失败: {e}")
                    return (idx, {}, str(e))

        results_list = await asyncio.gather(*[_proc(i, b) for i, b in enumerate(batches)])

        new_entries: dict = {}
        failed: list = []
        for idx, r, err in results_list:
            if err:
                failed.append({"batch": idx, "count": len(batches[idx]), "error": err})
            else:
                new_entries.update(r)

        cn_data = self._load_locale("cn")
        existing_keys = {k for k, _v, _t in self._flatten(cn_data)}
        added = 0
        skipped = 0
        for key, value in new_entries.items():
            if not isinstance(value, str) or key in existing_keys:
                skipped += 1
                continue
            await self._set_value_by_key(cn_data, key, value)
            existing_keys.add(key)
            added += 1

        self._save_locale("cn", cn_data)
        return {
            "scanned_count": len(raw_items), "added_count": added, "skipped_count": skipped,
            "batch_count": len(batches), "failed_batches": failed if failed else None,
        }

    # ─── 前端硬编码扫描（旧，保留兼容） ──────────────────────────
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