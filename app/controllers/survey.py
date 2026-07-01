"""调研问卷 Controller"""
import asyncio
import json
import os
import re
import secrets
import subprocess
import tempfile
import time
import uuid
from typing import Dict, List, Optional, Tuple

from tortoise.expressions import Q

from app.core.crud import CRUDBase
from app.log import logger
from app.models.admin import AIProxy, Skill, Survey, SurveySubmission, User
from app.schemas.survey import SurveyCreate, SurveySubmissionCreate, SurveyUpdate
from app.settings.config import settings

# 问卷网页文件存放目录
SURVEY_WEB_DIR = os.path.join(settings.BASE_DIR, "uploads", "static_web")


# ── 进度状态文件目录 ──
CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "cache")
SURVEY_PROGRESS_DIR = os.path.join(CACHE_DIR, "survey_create")
os.makedirs(SURVEY_PROGRESS_DIR, exist_ok=True)

# 内存中正在运行的任务缓存
_running_tasks: Dict[str, dict] = {}

# Node.js 可用性标志（用于 JS 语法检查）
_NODE_AVAILABLE: Optional[bool] = None


def _check_node_available() -> bool:
    """检测 Node.js 是否可用，结果缓存。"""
    global _NODE_AVAILABLE
    if _NODE_AVAILABLE is None:
        try:
            subprocess.run(
                ["node", "--version"],
                capture_output=True,
                timeout=5,
            )
            _NODE_AVAILABLE = True
        except (FileNotFoundError, OSError, subprocess.TimeoutExpired):
            _NODE_AVAILABLE = False
            logger.warning("Node.js 不可用，JS 语法检查将被跳过。如需启用，请在服务器上安装 Node.js。")
    return _NODE_AVAILABLE


def _progress_file(task_id: str) -> str:
    return os.path.join(SURVEY_PROGRESS_DIR, f"{task_id}.json")


def _save_progress(task_id: str, progress: dict):
    with open(_progress_file(task_id), "w", encoding="utf-8") as f:
        json.dump(progress, f, ensure_ascii=False, indent=2)


def _load_progress(task_id: str) -> dict:
    if task_id in _running_tasks:
        return dict(_running_tasks[task_id])
    pf = _progress_file(task_id)
    if os.path.exists(pf):
        try:
            with open(pf, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return {"status": "not_found", "progress": 0, "phase": "", "message": ""}


def _update_progress(task_id: str, status: str, phase: str, progress: int, message: str, detail: str = ""):
    p = {
        "task_id": task_id,
        "status": status,
        "phase": phase,
        "progress": progress,
        "message": message,
        "detail": detail,
        "started_at": _running_tasks.get(task_id, {}).get("started_at", time.time()),
        "done_at": time.time() if status in ("done", "error") else None,
    }
    _running_tasks[task_id] = p
    _save_progress(task_id, p)

# AI 生成问卷网页的 System Prompt（引擎模板由后端自动注入，此处只含约束）
AI_SURVEY_SYSTEM_PROMPT = """根据用户需求，创建用户调查问卷网页。系统会自动注入问卷引擎（数据采集/保存恢复/提交/动态表格管理）。

## 核心规则

1. 只输出完整的 HTML 文件（从 <!DOCTYPE html> 开始）
2. **禁止引入任何外部 JS/CSS 文件**（<link> 或 <script src>）
3. 在 </body> 之前，必须按顺序包含：
   (a) __SURVEY_CONFIG__ 配置脚本：
       <script>
       window.__SURVEY_CONFIG__ = { surveyToken: '__SURVEY_TOKEN__' };
       </script>
   (b) 占位符 <!--ENGINE_PLACEHOLDER-->（系统在此自动注入引擎，你不需要包含引擎代码）
   (c) 自定义业务交互脚本（如有特殊验证、条件显示等需求）
4. 必须包含两个按钮，class 精确为 sv-save 和 sv-submit

## 数据命名规范

- 所有表单控件必须同时设置 id 和 name 属性
- 普通字段（text/textarea/select/date 等）：key 取 id，value 取控件值
- 单选组（radio）：同组 name 相同，key 取 name，value 取选中项的 value
- 复选框组：同组 name 以 [] 结尾，保存为 {name: [选中值数组]}

## 可用全局 API（引擎注入后自动暴露）

  window.__engineCollectData()    - 收集所有表单数据返回 JSON
  window.__engineRestoreData(d)   - 恢复数据到表单
  window.__engineSaveLocal()      - 保存到 localStorage
  window.__engineRestoreLast()    - 从 localStorage 恢复
  window.__engineDoSubmit()       - 提交到服务器
  window.__engineShowToast(m,t)   - 显示提示 (m=消息,t=success|error|info)
  window.__engineAddTableRow(n)   - 向表格 n 添加一行

## 动态表格声明（无需写 JS，引擎自动管理）

  <!-- 表格声明 -->
  <table data-survey-table="表名" data-survey-columns="列名:类型,...">
    <thead><tr><th>列标题</th>...<th></th></tr></thead>
    <tbody></tbody>
  </table>
  <!-- 添加按钮声明 -->
  <button data-survey-table-add="表名">添加行</button>

  列类型: text(默认), number, date, select:选项1/选项2/...
  例如: data-survey-columns="事件:text,数量:number,日期:date,角色:select:员工/经理/总监"
  id 自动格式: {表名}_{列名}_{索引}  索引从 0 递增

## 样式与交互

- CSS 自由设计，必须内联（<style> 或 style 属性）
- 可编写自定义 script 实现验证、条件显示、动画等
- 交互结果必须反映到带 id 和 name 的控件上
- **sv-save / sv-submit 按钮必须固定在视口底部**（position: sticky; bottom: 0;），
  始终可见不随页面滚动消失。可使用半透明背景 + 上边框分隔，确保不与内容重叠。
- **禁止为 sv-save / sv-submit 按钮绑定 click 事件**：引擎已自动处理保存/提交，
  你添加的 handler 会导致重复提交。只需放置按钮本身即可，引擎会自动接管。

## 动态自定义项约定

- 动态添加的 checkbox 容器（如硬件方案自定义、待标注模型等）必须添加属性
  `data-survey-custom-container="字段name"`，如：
  `<div id="custom-hw-container" data-survey-custom-container="硬件方案[]"></div>`
  引擎在还原数据时，会在此容器中自动重建保存过的动态项，确保刷新后不丢失。

## 安全注意事项

- 禁止 import/export、eval、document.write、innerHTML 赋值
- 禁止在 <summary> 内放置交互式元素
- 确保所有内联 JavaScript 无语法错误

无需额外说明，直接输出完整代码。
"""

class SurveyController(CRUDBase[Survey, SurveyCreate, SurveyUpdate]):
    def __init__(self):
        super().__init__(model=Survey)

    # ── 短链接 ──
    @staticmethod
    def _gen_short_token() -> str:
        return secrets.token_hex(16)

    @staticmethod
    def short_url(token: str) -> str:
        return f"/api/sv/{token}"

    # ── 输出转换 ──
    def _to_output(self, obj: Survey) -> dict:
        return {
            "id": obj.id,
            "name": obj.name,
            "file_name": obj.file_name,
            "file_path": obj.file_path,
            "file_size": obj.file_size,
            "ai_proxy_id": obj.ai_proxy_id,
            "skill_id": obj.skill_id,
            "prompt": obj.prompt,
            "short_url_token": obj.short_url_token,
            "short_url": self.short_url(obj.short_url_token) if obj.short_url_token else None,
            "is_valid": obj.is_valid,
            "security_log": obj.security_log,
            "creator_id": obj.creator_id,
            "created_at": obj.created_at.isoformat() if obj.created_at else None,
            "updated_at": obj.updated_at.isoformat() if obj.updated_at else None,
        }

    # ── 通过短链接令牌获取 ──
    async def get_by_short_token(self, token: str) -> Optional[Survey]:
        return await self.model.filter(short_url_token=token, is_valid=True).first()

    # ── 用户可访问的问卷列表 ──
    async def list_accessible(self, user_id: int, page: int = 1, page_size: int = 50):
        is_super = await User.filter(id=user_id, is_superuser=True).exists()
        if is_super:
            qs = self.model.all()
        else:
            qs = self.model.filter(users__id=user_id)
        total = await qs.count()
        objs = await qs.offset((page - 1) * page_size).limit(page_size).order_by("-updated_at")
        return total, [self._to_output(obj) for obj in objs]

    # ── 更新授权用户 ──
    async def update_users(self, survey: Survey, user_ids: List[int]):
        await survey.users.clear()
        for uid in user_ids:
            u = await User.filter(id=uid).first()
            if u:
                await survey.users.add(u)

    # ── AI 创建问卷（异步后台，通过 progress 轮询结果）──
    @staticmethod
    def _inject_engine(html: str, short_token: str) -> str:
        """向 AI 生成的 HTML 注入引擎模板。

        引擎模板从 app/survey_assets/engine-template.js 读取，
        替换 <!--ENGINE_PLACEHOLDER--> 占位符（缺失时注入到 </body> 前），
        同时替换 __SURVEY_TOKEN__ 为真实 token。
        """
        import os as _os
        assets_dir = _os.path.join(
            _os.path.dirname(_os.path.dirname(__file__)), "survey_assets"
        )
        engine_path = _os.path.join(assets_dir, "engine-template.js")
        with open(engine_path, encoding="utf-8") as f:
            engine_js = f.read()

        inject_code = "<script>\n" + engine_js + "\n</script>"
        placeholder = "<!--ENGINE_PLACEHOLDER-->"

        if placeholder in html:
            html = html.replace(placeholder, inject_code)
        else:
            html = html.replace("</body>", inject_code + "\n</body>")

        return html.replace("__SURVEY_TOKEN__", short_token)

    async def start_create_survey(self, obj_in: SurveyCreate, creator_id: int) -> str:
        """启动异步问卷创建，返回 task_id。前端通过轮询获取进度和结果。"""
        # 预先校验 AI 代理
        proxy = await AIProxy.filter(id=obj_in.ai_proxy_id).first()
        if not proxy:
            raise ValueError("AI代理不存在")
        if not proxy.url or not proxy.token:
            raise ValueError("AI代理配置不完整，请检查 URL 和 Token")

        task_id = uuid.uuid4().hex[:12]
        _update_progress(task_id, "running", "preparing", 0, "任务已创建，正在准备...")

        # 后台异步执行
        asyncio.create_task(
            self._do_create_with_ai(
                task_id=task_id,
                obj_in=obj_in,
                creator_id=creator_id,
            )
        )
        return task_id

    async def _do_create_with_ai(
        self, task_id: str, obj_in: SurveyCreate, creator_id: int
    ):
        """后台执行 AI 创建问卷"""
        try:
            # ── 阶段 1: 准备 (0-10%) ──
            _update_progress(task_id, "running", "preparing", 5, "正在加载配置...")

            skill_content = ""
            if obj_in.skill_id:
                skill = await Skill.filter(id=obj_in.skill_id).first()
                if skill:
                    skill_content = f"\n\n## 以下为参考技能内容：\n{skill.content}"
                    _update_progress(task_id, "running", "preparing", 8, f"已加载 Skill")

            system_prompt = AI_SURVEY_SYSTEM_PROMPT + skill_content
            user_prompt = obj_in.prompt

            _update_progress(task_id, "running", "preparing", 10, "准备调用 AI...")

            # ── 阶段 2: AI 生成 (10-85%) ──
            proxy = await AIProxy.filter(id=obj_in.ai_proxy_id).first()

            # 传入进度回调，报告每个轮次的进度
            def _on_round(round_idx: int, total_rounds_estimate: int):
                base = 10
                span = 75  # 10 → 85
                pct = base + int(span * (round_idx + 1) / max(total_rounds_estimate, round_idx + 1))
                if round_idx == 0:
                    msg = "AI 正在生成问卷网页..."
                else:
                    msg = f"AI 生成内容较长，正在进行第 {round_idx + 1} 轮续写..."
                _update_progress(task_id, "running", "generating", min(pct, 85), msg)

            html_content = await self._call_ai_api(
                url=proxy.url,
                token=proxy.token,
                model=proxy.model or "deepseek-chat",
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                progress_callback=_on_round,
                max_tokens=proxy.max_tokens or 16384,
            )

            # ── JS 语法检查 + 自动修复（兜底机制）──
            js_errors = await self._validate_js_syntax(html_content)
            MAX_FIX_RETRIES = 2
            for fix_attempt in range(MAX_FIX_RETRIES):
                if not js_errors:
                    break
                logger.warning(
                    f"检测到 JS 语法错误，第 {fix_attempt + 1}/{MAX_FIX_RETRIES} 次自动修复: "
                    f"{len(js_errors)} 个错误"
                )
                _update_progress(
                    task_id, "running", "fixing", 86,
                    f"检测到 {len(js_errors)} 处 JS 语法错误，正在第 {fix_attempt + 1} 次自动修复..."
                )
                fix_prompt = (
                    "以下 HTML 中的 JavaScript 存在语法错误，请修复后输出完整的正确 HTML。\n\n"
                    "JS 语法错误：\n" + "\n".join(f"- {e}" for e in js_errors) + "\n\n"
                    "原始 HTML：\n```html\n" + html_content + "\n```"
                )
                html_content = await self._call_ai_api(
                    url=proxy.url,
                    token=proxy.token,
                    model=proxy.model or "deepseek-chat",
                    system_prompt="你是 HTML/JS 修复专家。只输出修复后的完整 HTML，不要任何解释。",
                    user_prompt=fix_prompt,
                    progress_callback=None,
                    max_tokens=proxy.max_tokens or 16384,
                )
                js_errors = await self._validate_js_syntax(html_content)

            if js_errors:
                logger.warning(
                    f"JS 语法错误修复失败（{MAX_FIX_RETRIES} 次重试后仍有 "
                    f"{len(js_errors)} 个错误），问卷已生成但可能存在问题"
                )

            _update_progress(task_id, "running", "generating", 86, "AI 生成完成，正在注入问卷引擎...")

            # ── 阶段 3: 注入引擎 + 安全审核 + 保存 (86-100%) ──
            short_token = self._gen_short_token()
            html_content = self._inject_engine(html_content, short_token)

            _update_progress(task_id, "running", "saving", 90, "正在进行安全审核...")
            from app.utils.survey_security import check_html_content
            security_result = check_html_content(html_content)
            _update_progress(task_id, "running", "saving", 93, "安全审核完成，正在保存文件...")

            os.makedirs(SURVEY_WEB_DIR, exist_ok=True)
            file_name = f"survey_{uuid.uuid4().hex[:12]}.html"
            file_path = os.path.join(SURVEY_WEB_DIR, file_name)

            with open(file_path, "w", encoding="utf-8") as f:
                f.write(html_content)

            file_size = os.path.getsize(file_path)

            _update_progress(task_id, "running", "saving", 95, "正在创建数据库记录...")

            security_log_json = json.dumps(security_result, ensure_ascii=False)
            survey = await self.model.create(
                name=obj_in.name,
                file_name=file_name,
                file_path=file_path,
                file_size=file_size,
                ai_proxy_id=obj_in.ai_proxy_id,
                skill_id=obj_in.skill_id,
                prompt=obj_in.prompt,
                short_url_token=short_token,
                is_valid=True,
                security_log=security_log_json,
                creator_id=creator_id,
            )

            if obj_in.user_ids:
                await self.update_users(survey, obj_in.user_ids)

            result = self._to_output(survey)
            result["security"] = security_result
            risk_count = len(security_result.get("issues", []))
            msg = "问卷创建成功"
            if risk_count:
                msg = f"问卷已生成，检测到 {risk_count} 条风险信息（未拦截）。"

            _update_progress(task_id, "done", "saving", 100, msg,
                             detail=json.dumps(result, ensure_ascii=False))
            # 保存结果到进度文件
            p = _load_progress(task_id)
            p["result"] = result
            _save_progress(task_id, p)

            logger.info(f"问卷创建完成: task_id={task_id}, survey_id={survey.id}, name={obj_in.name}")

        except Exception as e:
            logger.exception(f"问卷创建失败: task_id={task_id}")
            _update_progress(task_id, "error", "error", 0, "问卷创建失败", detail=str(e))

    @staticmethod
    def get_create_progress(task_id: str) -> dict:
        """获取问卷创建进度"""
        return _load_progress(task_id)

    @staticmethod
    async def get_create_result(task_id: str) -> Optional[dict]:
        """获取已创建的问卷结果"""
        progress = _load_progress(task_id)
        if progress.get("status") != "done":
            return None
        result = progress.get("result")
        if result:
            return result
        # 兜底：从 detail 中解析
        detail_str = progress.get("detail", "")
        if detail_str:
            try:
                return json.loads(detail_str)
            except json.JSONDecodeError:
                pass
        return None

    async def _call_ai_api(
        self,
        url: str,
        token: str,
        model: str,
        system_prompt: str,
        user_prompt: str,
        progress_callback=None,
        max_tokens: int = 16384,
    ) -> str:
        """调用 AI API 生成问卷网页（使用 openai SDK），支持自动续写被截断的回复"""
        from openai import OpenAI

        client = OpenAI(base_url=url, api_key=token)

        def _strip_code_fences(text: str) -> str:
            """Remove outermost markdown code fence wrappers from AI response."""
            t = text.strip()
            # Remove opening fence line: ```html, ```, etc.
            if t.startswith("```"):
                first_nl = t.find("\n")
                if first_nl != -1:
                    t = t[first_nl + 1:]
                else:
                    return ""  # lone fence line, no content
            # Remove closing fence line: ``` at the end
            if t.rstrip().endswith("```"):
                t = t.rstrip()[:-3].rstrip()
            return t

        def _strip_preamble(text: str) -> str:
            """Strip leading conversational preamble that is not HTML.
            Some AI models prepend phrases like '继续完成HTML代码：' before the
            actual continuation HTML.  Find the first '<' that starts an HTML
            tag (opening, closing, or doctype) and discard everything before it."""
            t = text.strip()
            m = re.search(r'<\s*(?:!|/|[a-zA-Z])', t)
            if m:
                t = t[m.start():]
            return t

        def _sync_call():
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ]

            all_content = ""
            max_rounds = 5  # 最多续写 5 轮，防止无限循环

            for round_idx in range(max_rounds):
                # 通过回调通知前端当前轮次（用于进度弹窗显示"第N轮续写"）
                if progress_callback:
                    progress_callback(round_idx, max_rounds)

                response = client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=0.7,
                    max_tokens=max_tokens,
                )

                choice = response.choices[0]
                raw_content = choice.message.content or ""
                # Strip markdown code fences and preamble from this round
                # before accumulating, otherwise the final regex extraction
                # would lose content from continuation rounds when round 1
                # was wrapped in ```html...```, and preamble text like
                # "继续完成HTML代码：" would pollute the final HTML.
                content = _strip_code_fences(raw_content)
                content = _strip_preamble(content)
                all_content += content
                finish_reason = choice.finish_reason

                logger.info(
                    f"AI 轮次 {round_idx + 1}: "
                    f"tokens={len(content)}, finish_reason={finish_reason}, "
                    f"累积长度={len(all_content)}"
                )

                if finish_reason != "length":
                    # 正常结束或触发了其他停止条件
                    break

                # finish_reason == "length"：内容被截断，需要继续
                # 追加 assistant 回复（使用原始内容保持历史准确）
                messages.append({"role": "assistant", "content": raw_content})
                # 续写指令：携带截断位置的末尾上下文，帮助 AI 精确定位续写起点
                tail = raw_content[-200:] if len(raw_content) > 200 else raw_content
                messages.append(
                    {"role": "user", "content": (
                        "上一轮输出在以下位置被硬截断（末尾200字符）：\n"
                        "```\n" + tail + "\n```\n"
                        "请从截断处精确继续，不要重复已输出的任何字符，"
                        "不要输出解释、前言或代码围栏，只输出纯HTML片段。"
                    )}
                )
            else:
                logger.warning(f"AI 续写达到最大轮次上限 {max_rounds}，可能内容仍未完整")

            if not all_content:
                raise ValueError("AI 返回内容为空")
            return all_content

        import asyncio
        html_content = await asyncio.to_thread(_sync_call)

        # 提取 HTML 代码块（如果 AI 将其包裹在 markdown 代码块中）
        html_match = re.search(r"```html\s*(.*?)\s*```", html_content, re.DOTALL)
        if html_match:
            return html_match.group(1).strip()

        # 否则，尝试提取 <!DOCTYPE html> 之后的所有内容
        doctype_match = re.search(r"<!DOCTYPE html>.*", html_content, re.DOTALL | re.IGNORECASE)
        if doctype_match:
            return doctype_match.group(0).strip()

        return html_content.strip()

    @staticmethod
    async def _validate_js_syntax(html: str) -> list:
        """检查 HTML 中所有 script 块的 JS 语法，返回错误信息列表（空列表表示无错误）。
        通过 node --check 实现，跳过第一个 script 块（配置脚本）和空块。
        如果 Node.js 不可用，跳过检查并返回空列表。"""
        if not _check_node_available():
            return []
        scripts = re.findall(r"<script>(.*?)</script>", html, re.DOTALL)
        errors = []

        for i, js in enumerate(scripts):
            js_stripped = js.strip()
            if not js_stripped:
                continue
            # 跳过纯配置脚本（第一个 script 块通常是 __SURVEY_CONFIG__）
            if i == 0 and "window.__SURVEY_CONFIG__" in js_stripped:
                continue

            def _check():
                result = subprocess.run(
                    ["node", "--check", "-"],
                    input=js_stripped,
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                return result

            try:
                result = await asyncio.to_thread(_check)
            except subprocess.TimeoutExpired:
                errors.append(f"Script 块 {i} 语法检查超时")
                continue

            if result.returncode != 0:
                # 格式化错误信息，只取前 300 字符
                err_text = result.stderr.strip()[:300]
                errors.append(f"Script 块 {i}: {err_text}")

        return errors

    # ── 更新问卷 ──
    async def update_survey(self, survey_id: int, obj_in: SurveyUpdate) -> dict:
        survey = await self.model.filter(id=survey_id).first()
        if not survey:
            raise ValueError("问卷不存在")

        update_data = obj_in.model_dump(exclude_unset=True)
        user_ids = update_data.pop("user_ids", None)

        if update_data:
            await survey.update_from_dict(update_data).save()

        if user_ids is not None:
            await self.update_users(survey, user_ids)

        return self._to_output(survey)

    # ── 删除问卷 ──
    async def delete_survey(self, survey_id: int) -> bool:
        survey = await self.model.filter(id=survey_id).first()
        if not survey:
            return False
        # 删除网页文件和所有提交记录
        if survey.file_path and os.path.exists(survey.file_path):
            try:
                os.remove(survey.file_path)
            except OSError:
                logger.warning(f"删除问卷文件失败: {survey.file_path}")
        await SurveySubmission.filter(survey_id=survey_id).delete()
        await survey.delete()
        return True

    # ── 提交记录 ──

    async def create_submission(self, obj_in: SurveySubmissionCreate) -> dict:
        """提交问卷数据 — v3.0 content 为 JSON 文本"""
        survey = await self.model.filter(short_url_token=obj_in.survey_token, is_valid=True).first()
        if not survey:
            raise ValueError("问卷不存在或已失效")

        # 取 raw_data 第一个字段的值作为标题
        title = None
        raw = obj_in.raw_data or {}
        if raw:
            first_val = list(raw.values())[0] if raw else None
            if first_val is not None and str(first_val).strip():
                title = str(first_val).strip()[:500]

        submission = await SurveySubmission.create(
            survey_id=survey.id,
            submitter_name=obj_in.submitter_name or "匿名",
            submitter_info=obj_in.submitter_info or {},
            title=title,
            content=obj_in.content,
            word_count=obj_in.word_count or len(obj_in.content.replace(" ", "").replace("\n", "")),
            raw_data=obj_in.raw_data or {},
            save_type=obj_in.save_type,
        )
        return {
            "id": submission.id,
            "survey_id": submission.survey_id,
            "submitter_name": submission.submitter_name,
            "title": submission.title,
            "content": submission.content,
            "word_count": submission.word_count,
            "save_type": submission.save_type,
            "created_at": submission.created_at.isoformat() if submission.created_at else None,
        }

    async def list_submissions(
        self, survey_id: int, page: int = 1, page_size: int = 50,
        save_type: Optional[str] = None,
    ) -> tuple:
        """获取问卷的提交记录列表"""
        q = Q(survey_id=survey_id)
        if save_type:
            q &= Q(save_type=save_type)
        total = await SurveySubmission.filter(q).count()
        objs = await (
            SurveySubmission.filter(q)
            .offset((page - 1) * page_size)
            .limit(page_size)
            .order_by("-created_at")
        )
        data = []
        for s in objs:
            data.append({
                "id": s.id,
                "survey_id": s.survey_id,
                "submitter_name": s.submitter_name,
                "submitter_info": s.submitter_info,
                "title": s.title,
                "content": s.content,
                "word_count": s.word_count,
                "raw_data": s.raw_data,
                "save_type": s.save_type,
                "created_at": s.created_at.isoformat() if s.created_at else None,
                "updated_at": s.updated_at.isoformat() if s.updated_at else None,
            })
        return total, data

    async def get_submission(self, submission_id: int) -> Optional[dict]:
        """获取单个提交记录的完整数据（含问卷名称等信息）"""
        sub = await SurveySubmission.filter(id=submission_id).first()
        if not sub:
            return None
        survey = await sub.survey.first()
        return {
            "id": sub.id,
            "survey_id": sub.survey_id,
            "survey_name": survey.name if survey else None,
            "submitter_name": sub.submitter_name,
            "submitter_info": sub.submitter_info,
            "title": sub.title,
            "content": sub.content,
            "word_count": sub.word_count,
            "raw_data": sub.raw_data,
            "save_type": sub.save_type,
            "created_at": sub.created_at.isoformat() if sub.created_at else None,
            "updated_at": sub.updated_at.isoformat() if sub.updated_at else None,
        }

    async def delete_submission(self, submission_id: int) -> bool:
        sub = await SurveySubmission.filter(id=submission_id).first()
        if not sub:
            return False
        await sub.delete()
        return True

    # ── 获取问卷网页内容（用于预览还原）──
    async def get_survey_html(self, survey_id: int) -> Optional[str]:
        survey = await self.model.filter(id=survey_id).first()
        if not survey or not survey.file_path:
            return None
        if not os.path.exists(survey.file_path):
            return None
        with open(survey.file_path, "r", encoding="utf-8") as f:
            return f.read()


survey_controller = SurveyController()
