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



logger = logging.getLogger(__name__)

# i18n 消息文件目录（相对于项目根目录）
_MESSAGES_DIR = Path(__file__).resolve().parent.parent.parent / "web" / "i18n" / "messages"
_INDEX_JS = _MESSAGES_DIR / "index.js"

def _get_project_root() -> Path:
    """获取项目根目录"""
    return Path(__file__).resolve().parent.parent.parent


def _is_valid_scan_text(text: str) -> bool:
    """验证扫描到的文本是否是有效的待翻译文本。

    过滤规则：
    - 必须包含中文
    - 长度 ≥ 1
    - 排除纯变量/表达式/符号
    - 排除已国际化的引用 t('...') / $t('...')
    - 排除纯数字/符号组合
    """
    import re
    text = text.strip()
    if not text:
        return False
    if not re.search(r'[\u4e00-\u9fff]', text):
        return False
    # 排除已国际化的引用
    if re.search(r'\b(?:t|_t|\$t|i18n\.global\.t)\s*\(', text):
        return False
    # 排除纯数字/符号组合（无中文）
    if re.match(r'^[\d\s\.\,\-\+\%\/\(\)\[\]\{\}\|&;:]+$', text):
        return False
    # 排除 date-fns / dayjs 格式字符串（只有符号和字母）
    if re.match(r'^[YMDdhmsaHkS\s\-\/\.:]+$', text):
        return False
    return True


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


    # ─── 通用正则扫描（不依赖前端 Vite / npm 包）───────────────

    # 扫描时跳过的目录名（相对于 web/src/）
    _SCAN_EXCLUDE_DIRS = frozenset({
        "node_modules", "dist", "public", "lib", "i18n", ".git",
        "__pycache__", "assets", "locales",
    })
    # 扫描的文件扩展名
    _SCAN_EXTENSIONS = frozenset({".vue", ".js", ".ts", ".jsx", ".tsx"})
    # 在模板中预期已国际化的属性（title/placeholder/label/alt 除外——它们仍需要扫描）
    _SCAN_SKIP_ATTRS = frozenset({"class", "style", "id", "ref", "key", "name", "type", "href", "src"})

    async def scan_frontend(
        self, skip_existing_values: bool = False
    ) -> Dict[str, Any]:
        """递归扫描 web/src/ 下所有前端文件，提取硬编码中文字符串。

        不依赖 @cybersailor/i18n-detect-vue（npm 包），使用 Python 正则扫描，
        覆盖率更高，始终可用。返回结构化列表供预览/批量处理。

        Args:
            skip_existing_values: True=跳过 cn.json 中已存在的值（类型B仅新字段）；
                                  False=包含所有，已存在值标记 existing_key。

        返回格式：
        {
            "total": 123,
            "new_count": 31,       // 不在 cn.json 中的新字段数
            "existing_count": 15,  // 已在 cn.json 中的字段数（可替换引用）
            "items": [
                {
                    "file": "web/src/views/xxx/index.vue",
                    "line": 42,
                    "text": "新建工作区",
                    "context": "...",
                    "prefix": "views.xxx.index",
                    "source": "html-inline",
                    "existing_key": null | "views.xxx.some_key",  // 已存在时非 null
                },
                ...
            ]
        }
        """
        import re
        import os as _os

        project_root = _get_project_root()
        src_dir = project_root / "web" / "src"
        if not src_dir.exists():
            return {"total": 0, "items": []}

        # 1. 收集所有目标文件
        files: list = []
        def _walk(d: Path):
            for entry in sorted(d.iterdir()):
                if entry.name.startswith("."):
                    continue
                if entry.is_dir():
                    if entry.name in self._SCAN_EXCLUDE_DIRS:
                        continue
                    _walk(entry)
                elif entry.is_file() and entry.suffix in self._SCAN_EXTENSIONS:
                    files.append(entry)

        _walk(src_dir)

        # 2. 加载 cn.json 已有值用于去重 + 构建 value→key 映射
        cn_data = self._load_locale("cn")
        existing_texts: set = set()
        text_to_existing_keys: dict = {}  # value → [key1, key2, ...]
        for k, v, _t in self._flatten(cn_data):
            if isinstance(v, str) and v.strip():
                existing_texts.add(v.strip())
                text_to_existing_keys.setdefault(v.strip(), []).append(k)

        # 3. 逐文件扫描
        all_items: list = []
        seen_in_file: set = set()  # (file, text) 去重

        for filepath in files:
            try:
                raw = filepath.read_text(encoding="utf-8")
            except Exception:
                continue

            rel = str(filepath.relative_to(project_root))
            is_vue = filepath.suffix == ".vue"
            lines = raw.split("\n")

            # 推导 prefix
            parts = tuple(rel.replace("\\", "/").split("/"))
            prefix = self._derive_prefix(parts)

            file_has_script_setup = bool(re.search(r"<script\s+setup[^>]*>", raw))

            # 跟踪 template/script 区域（用于设置正确的 source）
            in_template = False
            in_script = False

            line_start_pos = 0  # 当前行在文件中的字符偏移
            for line_no_1, line in enumerate(lines, 1):
                stripped = line.strip()

                # 跟踪 template/script 区域
                if is_vue:
                    if '<template>' in stripped:
                        in_template = True
                        in_script = False
                    elif '</template>' in stripped:
                        in_template = False
                    elif '<script' in stripped:
                        in_script = True
                        in_template = False
                    elif '</script>' in stripped:
                        in_script = False

                # 跳过空行、纯注释
                if not stripped:
                    line_start_pos += len(line) + 1  # 也更新空行的偏移！
                    continue
                if stripped.startswith("//") or stripped.startswith("<!--") or stripped.startswith("/*") or stripped.startswith("*"):
                    line_start_pos += len(line) + 1
                    continue
                # 跳过 import / export / console / defineOptions name
                if re.match(r"^(import\s|export\s|console\.)", stripped):
                    line_start_pos += len(line) + 1
                    continue
                if "defineOptions" in stripped and re.search(r"name\s*:", stripped):
                    line_start_pos += len(line) + 1
                    continue

                # ── 模式 1: 单引号字符串（含中文） ──
                for m in re.finditer(r"'([^']*[\u4e00-\u9fff][^']*)'", line):
                    text = m.group(1).strip()
                    if not text or len(text) < 1:
                        continue
                    # 排除已国际化的引用
                    before = line[:m.start()]
                    if re.search(r"\b(?:t|_t|\$t|i18n\.global\.t)\s*\(\s*$", before):
                        continue
                    if re.search(r"\bt\s*\(\s*['\"]", text):
                        continue
                    if not _is_valid_scan_text(text):
                        continue
                    src = "js-string"
                    if is_vue and in_template:
                        src = "html-inline"
                    self._add_scan_item(all_items, seen_in_file, rel, line_no_1, text, stripped, prefix, src,
                                         start=line_start_pos + m.start(), end=line_start_pos + m.end())

                # ── 模式 2: 双引号字符串（含中文） ──
                for m in re.finditer(r'"([^"]*[\u4e00-\u9fff][^"]*)"', line):
                    text = m.group(1).strip()
                    if not text or len(text) < 1:
                        continue
                    before = line[:m.start()]
                    # 跳过 HTML attribute 中的双引号（如 class="..."）
                    if re.search(r'\b(?:' + '|'.join(self._SCAN_SKIP_ATTRS) + r')\s*=\s*$', before):
                        continue
                    # 排除已国际化的引用
                    if re.search(r"\b(?:t|_t|\$t|i18n\.global\.t)\s*\(\s*$", before):
                        continue
                    if re.search(r'\bt\s*\(\s*["\']', text):
                        continue
                    if not _is_valid_scan_text(text):
                        continue
                    if is_vue and in_script:
                        source = "js-string"
                    else:
                        source = "html-attribute" if re.search(r'\b(?:title|placeholder|label|alt|action|summary|description)\s*=\s*$', before) else "js-string"
                        if not is_vue and source == "html-attribute":
                            source = "js-string"
                    self._add_scan_item(all_items, seen_in_file, rel, line_no_1, text, stripped, prefix, source,
                                         start=line_start_pos + m.start(), end=line_start_pos + m.end())

                # ── 模式 3: HTML 属性值（title/placeholder/label/alt/action/summary/description） ──
                for m in re.finditer(r'\b(title|placeholder|label|alt|action|summary|description)="([^"]*[\u4e00-\u9fff][^"]*)"', line):
                    text = m.group(2).strip()
                    if not text or len(text) < 1:
                        continue
                    if not _is_valid_scan_text(text):
                        continue
                    self._add_scan_item(all_items, seen_in_file, rel, line_no_1, text, stripped, prefix, "html-attribute",
                                         start=line_start_pos + m.start(2), end=line_start_pos + m.end(2))

                # ── 模式 4: 标签间文本（含中文，不含 {{ }} 插值） ──
                for m in re.finditer(r'(?:>|/>)\s*([^<{]*[\u4e00-\u9fff][^<{]*?)<', line):
                    text = m.group(1).strip()
                    if not text or len(text) < 1:
                        continue
                    # 只取纯中文文本（不含 HTML 标签、不含变量引用）
                    if re.search(r'<[^>]+>', text):
                        continue
                    if not _is_valid_scan_text(text):
                        continue
                    self._add_scan_item(all_items, seen_in_file, rel, line_no_1, text, stripped, prefix, "html-inline",
                                         start=line_start_pos + m.start(1), end=line_start_pos + m.end(1))

                # ── 模式 5: Vue 模板插值 {{ ... }} ──
                if is_vue:
                    for m in re.finditer(r'\{\{\s*([^}]*[\u4e00-\u9fff][^}]*?)\s*\}\}', line):
                        text = m.group(1).strip()
                        if not text or len(text) < 1:
                            continue
                        # 排除 $t('...')
                        if re.search(r'\$t\s*\(', text):
                            continue
                        if not _is_valid_scan_text(text):
                            continue
                        self._add_scan_item(all_items, seen_in_file, rel, line_no_1, text, stripped, prefix, "template-interpolation",
                                             start=line_start_pos + m.start(1), end=line_start_pos + m.end(1))

                # ── 模式 6: JSX / h() 中的中文文本节点 ──
                if not is_vue or file_has_script_setup:
                    for m in re.finditer(r'>\s*([\u4e00-\u9fff][^<]*?)</', line):
                        text = m.group(1).strip()
                        if not text or len(text) < 2:
                            continue
                        if not _is_valid_scan_text(text):
                            continue
                        self._add_scan_item(all_items, seen_in_file, rel, line_no_1, text, stripped, prefix, "html-inline",
                                            start=line_start_pos + m.start(1), end=line_start_pos + m.end(1))

                line_start_pos += len(line) + 1  # 更新行偏移（含换行符）—— 必须在 for line_no_1 循环体内

            # 每处理一个文件清理 seen 中的 file 专属去重（只在函数级别去重）
            # seen_in_file 已经是全局的 (file, text) 去重，保留

        # 5. 按 cn.json 已有值处理
        for item in all_items:
            text = item["text"].strip()
            if text in text_to_existing_keys:
                # 已存在：优先选同 prefix 的 key，否则取第一个
                keys = text_to_existing_keys[text]
                # 启发式匹配：选与当前 prefix 最接近的 key
                best_key = keys[0]
                for k in keys:
                    if k.startswith(item["prefix"]):
                        best_key = k
                        break
                item["existing_key"] = best_key

        # 分类统计
        new_items = [it for it in all_items if not it.get("existing_key")]
        existing_items = [it for it in all_items if it.get("existing_key")]

        # 6. 按文件+行号排序
        if skip_existing_values:
            items = new_items
        else:
            items = new_items + existing_items
        items.sort(key=lambda x: (x["file"], x["line"]))

        return {
            "total": len(items),
            "new_count": len(new_items),
            "existing_count": len(existing_items),
            "items": items,
        }

    @staticmethod
    def _add_scan_item(
        all_items: list, seen: set,
        rel: str, line_no: int, text: str,
        line_content: str, prefix: str, source: str,
        start: int | None = None,
        end: int | None = None,
    ) -> dict:
        """添加一条扫描结果，自动去重。返回添加的条目（或 None 如果已跳过）。"""
        dedup_key = (rel, text.strip())
        if dedup_key in seen:
            return None
        seen.add(dedup_key)
        item = {
            "file": rel,
            "line": line_no,
            "text": text.strip(),
            "context": line_content[:200],
            "prefix": prefix,
            "source": source,
            "existing_key": None,
            "start": start,
            "end": end,
        }
        all_items.append(item)
        return item

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

    async def process_scan(
        self, ai_proxy_name: str, items: List[dict], safe_mode: bool = True
    ) -> Dict[str, Any]:
        """接收扫描结果，AI 生成 key 后追加到 cn.json。

        safe_mode=True (默认): 只写 cn.json，不修改源 Vue 文件。编译通过后再手动或通过脚本回写。
        safe_mode=False: 同时回写源文件（将硬编码中文替换为 $t('key')）。

        ai_proxy_name: 类型B（新字段）需要 AI 代理；纯类型A 时可为空字符串。
        """
        from app.controllers.ai_proxy import ai_proxy_controller

        # 1. 分离两类条目：有 existing_key 的（类型A）直接替换，无 key 的（类型B）走 AI
        cn_data = self._load_locale("cn")
        existing_keys = {k for k, _v, _t in self._flatten(cn_data)}
        existing_texts = {v for _k, v, _t in self._flatten(cn_data) if isinstance(v, str) and v.strip()}

        existing_replacements = []  # 类型A: (start, end, text, existing_key, source, file)
        new_items = []              # 类型B: 需要 AI 生成 key
        seen_new = set()

        for it in items:
            text = (it.get("text") or "").strip()
            file = it.get("file", "")
            existing_key = it.get("existing_key")
            start = it.get("start")
            end = it.get("end")
            source = it.get("source", "")

            if not text or len(text) < 1:
                continue

            # 类型A: 已有 key，直接加入替换列表
            if existing_key:
                dedup_key = (text, file, existing_key)
                if dedup_key not in seen_new:
                    seen_new.add(dedup_key)
                    existing_replacements.append({
                        "text": text, "existing_key": existing_key,
                        "start": start, "end": end, "source": source, "file": file,
                    })
                continue

            # 类型B: 需要 AI 生成 key
            if text in existing_texts:
                continue
            dedup_key = (text, file)
            if dedup_key in seen_new:
                continue
            seen_new.add(dedup_key)
            parts = tuple(file.replace("\\", "/").split("/"))
            prefix = self._derive_prefix(parts)
            new_items.append({"text": text, "prefix": prefix, "file": file,
                              "start": start, "end": end, "source": source})

        # 2. 类型A: 直接替换源文件（无需 AI，无需写 cn.json）
        direct_replaced = 0
        if existing_replacements and not safe_mode:
            # 构建 text_to_key 映射用于 _replace_in_source_files
            # _replace_in_source_files 按 processed 列表中的 start/end 替换
            # 这里直接用 existing_key 作为 key
            text_to_key = {}
            processed_for_replace = []
            for rp in existing_replacements:
                text_to_key[rp["text"]] = rp["existing_key"]
                processed_for_replace.append({
                    "text": rp["text"],
                    "start": rp["start"],
                    "end": rp["end"],
                    "source": rp["source"],
                    "file": rp["file"],
                })
            if processed_for_replace:
                direct_replaced = self._replace_in_source_files(
                    processed_for_replace, text_to_key
                )
                logger.info(
                    f"类型A 直接替换: {direct_replaced} 处，"
                    f"涉及 {len(existing_replacements)} 个条目"
                )
        elif existing_replacements and safe_mode:
            logger.info(
                f"safe_mode: 跳过类型A 源文件替换，"
                f"共 {len(existing_replacements)} 个条目已有 key"
            )

        # 3. 类型B: 需要 AI 生成 key（只有存在类型B 时才获取 AI 代理）
        added = 0
        skipped = 0
        batch_count = 0
        failed = None
        ai_replaced = 0

        if new_items:
            proxy = await ai_proxy_controller.get_by_name(ai_proxy_name)
            if not proxy:
                raise ValueError(f"AI 代理 '{ai_proxy_name}' 不存在（类型B 新字段需要 AI 生成 key）")
            import asyncio
            # 异步并发控制：如果 proxy 为 None（类型A不需要），跳过 AI 调用
            batches = [new_items[i:i + self._SCAN_BATCH_SIZE] for i in range(0, len(new_items), self._SCAN_BATCH_SIZE)]
            batch_count = len(batches)
            sys_prompt = self._build_scan_add_system_prompt()
            sem = asyncio.Semaphore(self._SCAN_MAX_CONCURRENT)

            async def _proc(idx: int, batch: list):
                async with sem:
                    inp = [{"text": it["text"], "prefix": it["prefix"], "file": it["file"]} for it in batch]
                    user = f"请为以下中文 UI 文本生成合适的 i18n key：\n{json.dumps(inp, ensure_ascii=False, indent=2)}"
                    try:
                        r = await self._call_ai(proxy, sys_prompt, user)
                        p = self._extract_json(r)
                        return (idx, p if isinstance(p, dict) else {}, None if isinstance(p, dict) else f"批次 {idx} 非字典")
                    except Exception as e:
                        logger.error(f"process_scan 批次 {idx} 失败: {e}")
                        return (idx, {}, str(e))

            results_list = await asyncio.gather(*[_proc(i, b) for i, b in enumerate(batches)])

            new_entries = {}
            failed = []
            for idx, r, err in results_list:
                if err:
                    failed.append({"batch": idx, "count": len(batches[idx]), "error": err})
                else:
                    new_entries.update(r)

            # 4. 追加到 cn.json（去重）
            for key, value in new_entries.items():
                if not isinstance(value, str) or key in existing_keys:
                    skipped += 1
                    continue
                await self._set_value_by_key(cn_data, key, value)
                existing_keys.add(key)
                added += 1

            self._save_locale("cn", cn_data)

            # 5. 类型B 回写源文件
            if added > 0:
                text_to_key = {v: k for k, v in new_entries.items() if isinstance(v, str)}
                if safe_mode:
                    logger.info(f"safe_mode: 跳过类型B源文件回写，已添加 {added} 条 key 到 cn.json")
                else:
                    ai_replaced = self._replace_in_source_files(new_items, text_to_key)

        return {
            "scanned_count": len(items),
            "added_count": added,
            "replaced_count": direct_replaced + ai_replaced,
            "direct_replaced_count": direct_replaced,      # 类型A 直接替换
            "ai_replaced_count": ai_replaced,              # 类型B AI 替换
            "existing_replacements_count": len(existing_replacements),  # 类型A 条目数
            "skipped_count": skipped,
            "batch_count": batch_count,
            "failed_batches": failed if failed else None,
            "safe_mode": safe_mode,
        }

    # ─── Git 回退 & 编译验证 ───────────────────────────────────

    @staticmethod
    def _git_modified_files() -> List[str]:
        """获取所有已修改但未 stage 的文件列表（相对于项目根目录）。"""
        import subprocess
        try:
            root = _get_project_root()
            out = subprocess.check_output(
                ["git", "diff", "--name-only"],
                cwd=str(root),
                text=True,
                timeout=10,
            )
            return [f for f in out.strip().split("\n") if f]
        except Exception:
            return []

    @staticmethod
    def _git_restore_files(files: List[str]) -> bool:
        """用 git checkout 回退指定文件到 HEAD 版本。

        只回退明确指定的文件，不使用全局 checkout。
        """
        import subprocess
        root = _get_project_root()
        ok = True
        for f in files:
            try:
                subprocess.check_call(
                    ["git", "checkout", "HEAD", "--", f],
                    cwd=str(root),
                    timeout=15,
                )
                logger.info(f"git checkout HEAD -- {f}")
            except Exception as e:
                logger.error(f"git checkout 失败 ({f}): {e}")
                ok = False
        return ok

    @staticmethod
    def _verify_frontend_build() -> Dict[str, Any]:
        """运行 pnpm build 验证编译。

        Returns:
            {
                "ok": True/False,
                "exit_code": 0/1,
                "stdout_tail": "...",
                "stderr_tail": "...",
            }
        """
        import subprocess
        root = _get_project_root()
        web_dir = root / "web"
        try:
            proc = subprocess.run(
                ["pnpm", "build"],
                cwd=str(web_dir),
                capture_output=True,
                text=True,
                timeout=300,
            )
            tail_stdout = "\n".join(proc.stdout.strip().split("\n")[-20:]) if proc.stdout else ""
            tail_stderr = "\n".join(proc.stderr.strip().split("\n")[-20:]) if proc.stderr else ""
            return {
                "ok": proc.returncode == 0,
                "exit_code": proc.returncode,
                "stdout_tail": tail_stdout,
                "stderr_tail": tail_stderr,
            }
        except subprocess.TimeoutExpired:
            return {"ok": False, "exit_code": -1, "stdout_tail": "", "stderr_tail": "pnpm build 超时 (>300s)"}
        except FileNotFoundError:
            return {"ok": False, "exit_code": -1, "stdout_tail": "", "stderr_tail": "pnpm 未安装或不在 PATH"}

    async def batch_delete(self, keys: List[str]) -> Dict[str, Any]:
        """从所有语言文件中批量删除指定 key 及其值"""
        locales = self._get_locales()
        locale_data = {loc: self._load_locale(loc) for loc in locales}
        deleted = 0
        for key in keys:
            key_deleted = False
            for loc in locales:
                if self._delete_key_by_path(locale_data[loc], key.split(".")):
                    key_deleted = True
            if key_deleted:
                for loc in locales:
                    self._save_locale(loc, locale_data[loc])
                deleted += 1
        await self._sync_index_js()
        return {"deleted": deleted}

    def _delete_key_by_path(self, data: dict, parts: list) -> bool:
        """按点分隔路径删除嵌套字典中的键，同时清理空的父节点"""
        if len(parts) == 1:
            return data.pop(parts[0], None) is not None
        key = parts[0]
        if key in data and isinstance(data[key], dict):
            if self._delete_key_by_path(data[key], parts[1:]):
                # 清理空的父节点
                if not data[key]:
                    del data[key]
                return True
        return False

    def _replace_in_source_files(self, processed: list, text_to_key: dict) -> int:
        """用 AI 生成的 key 替换源文件中的硬编码中文，并自动补全 i18n import

        替换规则：
        - .vue + html-inline   → {{ $t('key') }}    （模板中 $t 全局可用）
        - .vue + js-string 等  → t('key')           （需 useI18n）
        - .js/.ts + 任意       → i18n.global.t('key')（需 import i18n）
        """
        project_root = _get_project_root()

        by_file: dict = {}
        for it in processed:
            txt = it["text"]
            key = text_to_key.get(txt)
            start = it.get("start")
            end = it.get("end")
            source = it.get("source", "")
            if not key or start is None or end is None:
                continue
            f = it["file"]
            by_file.setdefault(f, []).append((start, end, txt, key, source))

        replaced = 0
        modified_files: set = set()
        for rel_path, replacements in by_file.items():
            filepath = project_root / rel_path  # rel 已是项目相对路径（如 web/src/...）
            if not filepath.exists():
                continue
            content = filepath.read_text(encoding="utf-8")
            is_vue = rel_path.endswith(".vue")
            # .js/.ts 中 t 是否已可用（已声明 const { t } = ...）
            has_t = bool(re.search(r"\bconst\s*\{\s*t\s*\}\s*=", content))

            for start, end, _txt, key, source in sorted(replacements, key=lambda x: -x[0]):
                if is_vue and source == "html-inline":
                    repl = "{{ $t('%s') }}" % key
                elif is_vue and source == "template-interpolation":
                    repl = "$t('%s')" % key
                elif is_vue and source == "html-attribute":
                    # 属性值替换需要保留引号（已在 start/end 外），值替换为 t('key')
                    repl = "t('%s')" % key
                elif is_vue:
                    repl = "t('%s')" % key
                elif has_t:
                    repl = "t('%s')" % key
                else:
                    repl = "i18n.global.t('%s')" % key
                content = content[:start] + repl + content[end:]
                replaced += 1

            filepath.write_text(content, encoding="utf-8")
            modified_files.add(rel_path)

        # 回写后补全 i18n import
        self._ensure_i18n_imports(modified_files)

        logger.info(f"_replace_in_source_files: 替换了 {replaced} 处，涉及 {len(by_file)} 个文件")
        return replaced

    def _ensure_i18n_imports(self, files: set):
        """确保修改后的文件有可用的 i18n 函数

        .vue 文件：检测是否有 `const { t } = useI18n()`，无则补全 import + 声明
        .js/.ts 文件：检测是否有 `import i18n from '~/i18n'`，无则补全
        """
        project_root = _get_project_root()
        web_src = project_root / "web"

        for rel_path in files:
            filepath = web_src / rel_path
            if not filepath.exists():
                continue
            content = filepath.read_text(encoding="utf-8")
            modified = False

            if rel_path.endswith(".vue"):
                # 仅当 script 中有 t('...') 调用时才需补全
                m_script = re.search(
                    r"<script\s+setup[^>]*>(.*?)</script>", content, re.DOTALL
                )
                if m_script:
                    script_body = m_script.group(1)
                    # 无 t(' 调用 → 只有模板 $t，无需 import
                    if not re.search(r"\bt\s*\(", script_body):
                        continue
                    # 已有 useI18n → 跳过
                    if "useI18n" in script_body and re.search(
                        r"\bconst\s*\{\s*t\s*\}\s*=\s*useI18n\s*\(", script_body
                    ):
                        continue
                    # 补全 import
                    if "from 'vue-i18n'" not in script_body:
                        script_body = (
                            "import { useI18n } from 'vue-i18n'\n" + script_body
                        )
                        modified = True
                    # 补全 const { t } = useI18n()（放在 imports 之后）
                    if not re.search(
                        r"\bconst\s*\{\s*t\s*\}\s*=\s*useI18n\s*\(", script_body
                    ):
                        # 找到 import 块结尾
                        lines = script_body.split("\n")
                        insert_at = 0
                        for i, line in enumerate(lines):
                            if line.strip().startswith("import "):
                                insert_at = i + 1
                            elif insert_at > 0 and not line.strip():
                                continue
                            elif insert_at > 0:
                                break
                        lines.insert(insert_at, "const { t } = useI18n()")
                        script_body = "\n".join(lines)
                        modified = True
                    if modified:
                        content = (
                            content[: m_script.start(1)]
                            + script_body
                            + content[m_script.end(1) :]
                        )
            else:
                # .js/.ts 文件
                if "import i18n from '~/i18n'" not in content:
                    content = "import i18n from '~/i18n'\n" + content
                    modified = True

            if modified:
                filepath.write_text(content, encoding="utf-8")
                logger.info(f"_ensure_i18n_imports: 补全 {rel_path}")


# 单例
i18n_controller = I18nController()