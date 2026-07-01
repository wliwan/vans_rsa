import asyncio
import json
import logging
import re
from typing import Optional

from app.core.crud import CRUDBase
from app.models.admin import Menu, MenuI18n
from app.schemas.menus import MenuCreate, MenuUpdate

logger = logging.getLogger(__name__)


class MenuController(CRUDBase[Menu, MenuCreate, MenuUpdate]):
    def __init__(self):
        super().__init__(model=Menu)

    async def get_by_menu_path(self, path: str) -> Optional["Menu"]:
        return await self.model.filter(path=path).first()


menu_controller = MenuController()


# ─── 菜单国际化控制器 ───────────────────────────────────────────────


class MenuI18nController:
    """菜单国际化控制器（非 CRUDBase，直接操作 MenuI18n 模型）"""

    # locale → 语言中文名映射（用于 AI 提示词）
    _LANG_NAME_MAP: dict[str, str] = {
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

    async def get_list(self, locale: str = "") -> dict:
        """获取菜单国际化列表

        locale 为空时返回所有语言；指定时只返回该语言。
        返回格式：{ menus: [...], translations: { menu_id: { locale: name } } }
        """
        menus = await Menu.all().order_by("order")
        menu_list = []
        for m in menus:
            menu_list.append({
                "id": m.id,
                "name": m.name,
                "path": m.path,
                "parent_id": m.parent_id,
                "menu_type": m.menu_type.value if m.menu_type else None,
                "order": m.order,
                "icon": m.icon,
            })

        # 查询翻译
        qs = MenuI18n.all()
        if locale:
            qs = qs.filter(locale=locale)
        translations_raw = await qs

        translations: dict[int, dict[str, str]] = {}
        for t in translations_raw:
            if t.menu_id not in translations:
                translations[t.menu_id] = {}
            translations[t.menu_id][t.locale] = t.name

        return {
            "menus": menu_list,
            "translations": translations,
        }

    async def save(self, menu_id: int, locale: str, name: str) -> dict:
        """保存/更新单条菜单翻译（upsert）"""
        # 检查菜单是否存在
        menu = await Menu.filter(id=menu_id).first()
        if not menu:
            raise ValueError(f"菜单 ID {menu_id} 不存在")

        existing = await MenuI18n.filter(menu_id=menu_id, locale=locale).first()
        if existing:
            existing.name = name
            await existing.save()
            return {"id": existing.id, "menu_id": menu_id, "locale": locale, "name": name, "action": "updated"}
        else:
            obj = await MenuI18n.create(menu_id=menu_id, locale=locale, name=name)
            return {"id": obj.id, "menu_id": menu_id, "locale": locale, "name": name, "action": "created"}

    async def delete(self, menu_id: int, locale: str) -> bool:
        """删除单条菜单翻译"""
        deleted = await MenuI18n.filter(menu_id=menu_id, locale=locale).delete()
        return deleted > 0

    async def export_data(self, locale: str) -> dict:
        """导出指定语言的菜单翻译"""
        translations = await MenuI18n.filter(locale=locale).prefetch_related("menu")
        entries = []
        for t in translations:
            menu = await t.menu
            entries.append({
                "menu_id": t.menu_id,
                "menu_name": menu.name if menu else "",
                "menu_path": menu.path if menu else "",
                "translated_name": t.name,
            })
        return {"locale": locale, "entries": entries}

    async def import_data(self, locale: str, entries: list[dict]) -> int:
        """导入菜单翻译数据（upsert）"""
        count = 0
        for entry in entries:
            menu_id = entry.get("menu_id")
            name = entry.get("name") or entry.get("translated_name")
            if not menu_id or not name:
                continue
            try:
                await self.save(menu_id=menu_id, locale=locale, name=name)
                count += 1
            except Exception as e:
                logger.warning(f"导入 menu_id={menu_id} locale={locale} 失败: {e}")
        return count

    # ─── AI 翻译 ───────────────────────────────────────────────────

    def _build_menu_translate_prompt(self, target_lang_name: str) -> str:
        """构建菜单翻译的 system prompt"""
        return (
            f"你是一位专业的 UI 本地化翻译专家。请将以下中文菜单名称翻译成{target_lang_name}。\n"
            "\n"
            "## 背景\n"
            "这些菜单名称来自 vue-fastapi-admin，一个基于 Vue 3 + Naive UI 的企业后台管理系统。\n"
            "菜单名称需要简洁、专业，适合侧边栏导航显示。\n"
            "\n"
            "## 翻译规范\n"
            "1. **简洁原则**：菜单名称应尽量简短，通常 1-3 个词。中文四字格可简化为英文 1-2 词\n"
            "   例如：「用户管理」→「Users」\n"
            "   例如：「角色管理」→「Roles」\n"
            "   例如：「菜单管理」→「Menus」\n"
            "   例如：「系统管理」→「System」\n"
            "   例如：「部门管理」→「Departments」\n"
            "2. **保持一致性**：同类型菜单使用相同命名风格\n"
            "3. **自然流畅**：翻译应符合目标语言的表达习惯\n"
            "4. **不修改 key**：只翻译 value，保持 JSON key 不变\n"
            "\n"
            "## 输出格式\n"
            "只返回一个 JSON 对象，key 为菜单 ID（数字字符串），value 为翻译后的菜单名称。\n"
            "不要添加任何解释、注释或 Markdown 代码块标记。"
        )

    async def ai_generate(
        self,
        proxy_name: str,
        target_locales: list[str],
        mode: str = "incremental",
    ) -> dict:
        """使用 AI 代理将菜单名翻译为目标语言"""
        from app.controllers.ai_proxy import ai_proxy_controller

        # 验证语言
        for loc in target_locales:
            if loc not in self._LANG_NAME_MAP:
                raise ValueError(
                    f"不支持的目标语言代码 '{loc}'，"
                    f"支持的语言: {', '.join(sorted(self._LANG_NAME_MAP.keys()))}"
                )

        # 获取 AI 代理
        proxy = await ai_proxy_controller.get_by_name(proxy_name)
        if not proxy:
            raise ValueError(f"AI 代理 '{proxy_name}' 不存在")

        # 获取所有菜单
        menus = await Menu.all().order_by("order")
        menu_dict: dict[int, str] = {}
        for m in menus:
            menu_dict[m.id] = m.name

        results: dict[str, dict] = {}

        for target_locale in target_locales:
            target_lang_name = self._LANG_NAME_MAP.get(target_locale, target_locale)
            pending_menus: dict[int, str] = {}

            if mode == "incremental":
                # 增量模式：只翻译尚未翻译的菜单
                existing = await MenuI18n.filter(locale=target_locale)
                existing_ids = {t.menu_id for t in existing}
                for mid, mname in menu_dict.items():
                    if mid not in existing_ids:
                        pending_menus[mid] = mname
            else:
                pending_menus = dict(menu_dict)

            if not pending_menus:
                results[target_locale] = {
                    "translated_count": 0,
                    "total_count": len(menu_dict),
                    "skipped_count": len(menu_dict),
                }
                continue

            # 构建用户消息（JSON 格式）
            user_prompt = json.dumps(
                {str(k): v for k, v in pending_menus.items()},
                ensure_ascii=False,
                indent=2,
            )

            system_prompt = self._build_menu_translate_prompt(target_lang_name)

            # 调用 AI
            max_tokens = proxy.max_tokens or 16384
            from openai import OpenAI

            client = OpenAI(base_url=proxy.url, api_key=proxy.token)
            model = proxy.model or "gpt-4"

            def _sync_call():
                response = client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": f"请翻译以下 JSON 中的值（只翻译 value，key 保持不变）：\n{user_prompt}"},
                    ],
                    max_tokens=max_tokens,
                    temperature=0.3,
                )
                return response.choices[0].message.content

            ai_response = await asyncio.to_thread(_sync_call)
            logger.info(f"AI菜单翻译响应({target_locale}, 前500字): {ai_response[:500]}")

            # 解析 AI 响应
            translated = self._extract_json(ai_response)
            if not isinstance(translated, dict):
                logger.warning(f"AI菜单翻译解析失败({target_locale}): {ai_response[:500]}")
                results[target_locale] = {
                    "translated_count": 0,
                    "total_count": len(menu_dict),
                    "skipped_count": 0,
                    "error": "AI 返回格式异常",
                }
                continue

            # 保存翻译
            saved_count = 0
            for key_str, name in translated.items():
                try:
                    mid = int(key_str)
                    if mid in menu_dict and isinstance(name, str) and name.strip():
                        await self.save(menu_id=mid, locale=target_locale, name=name.strip())
                        saved_count += 1
                except (ValueError, Exception) as e:
                    logger.warning(f"保存菜单翻译失败 menu_id={key_str} locale={target_locale}: {e}")

            results[target_locale] = {
                "translated_count": saved_count,
                "total_count": len(menu_dict),
                "skipped_count": len(menu_dict) - len(pending_menus),
            }

        return results

    def _extract_json(self, text: str) -> dict | None:
        """从 AI 回复中提取 JSON"""
        text = text.strip()
        try:
            result = json.loads(text)
            if isinstance(result, dict):
                return result
        except json.JSONDecodeError:
            pass

        # 尝试提取 ```json ... ``` 块
        m = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
        if m:
            try:
                result = json.loads(m.group(1))
                if isinstance(result, dict):
                    return result
            except json.JSONDecodeError:
                pass

        # 尝试提取 { ... } 块
        m = re.search(r"\{.*\}", text, re.DOTALL)
        if m:
            try:
                result = json.loads(m.group(0))
                if isinstance(result, dict):
                    return result
            except json.JSONDecodeError:
                pass

        return None

    async def get_translated_name(self, menu_id: int, locale: str) -> str | None:
        """获取指定菜单在指定语言下的翻译名"""
        t = await MenuI18n.filter(menu_id=menu_id, locale=locale).first()
        return t.name if t else None


menu_i18n_controller = MenuI18nController()
