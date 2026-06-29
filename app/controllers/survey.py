"""调研问卷 Controller"""
import asyncio
import json
import os
import re
import secrets
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
SURVEY_LIB_URL = "/api/v1/survey/static/survey-lib.js"
# SURVEY_CSS_URL 已废弃 — v2.0 不再要求 AI 引入 CSS 文件
# 保留路由和文件仅为向后兼容旧版问卷

# ── 进度状态文件目录 ──
CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "cache")
SURVEY_PROGRESS_DIR = os.path.join(CACHE_DIR, "survey_create")
os.makedirs(SURVEY_PROGRESS_DIR, exist_ok=True)

# 内存中正在运行的任务缓存
_running_tasks: Dict[str, dict] = {}


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

# AI 生成问卷网页的 System Prompt
AI_SURVEY_SYSTEM_PROMPT = """根据用户需求，创建用户调查问卷网页。

## 核心规则（必须遵守，否则问卷无法正常工作）

1. 只输出完整的 HTML 文件（从 <!DOCTYPE html> 开始）
2. **不需要引入任何外部 JS/CSS 文件**，所有逻辑和样式全部内联在 HTML 中。
3. 在 </body> 之前，必须按顺序包含：
   (a) __SURVEY_CONFIG__ 配置脚本（不可省略，__SURVEY_TOKEN__ 会被后端替换为真实 token）：
       <script>
         window.__SURVEY_CONFIG__ = { surveyToken: '__SURVEY_TOKEN__' };
       </script>
   (b) 问卷核心逻辑脚本（参见下方「内联 JS 模板」）。
   (c) 业务交互脚本（你的自定义表单交互逻辑）。
4. 页面底部必须有两个按钮，class 必须精确为：
   <button class="sv-save">保存草稿</button>
   <button class="sv-submit">提交问卷</button>
   （JS 通过这两个 class 绑定点击事件，不可改名）
5. 所有表单控件（input、textarea、select）必须设置 **id 和 name 属性**。
   - **id**：唯一标识，优先通过 id 保存和恢复数据。
     动态添加的元素也必须分配唯一 id（建议用递增索引，如 items_0_name、items_1_name）。
   - **name**：表单提交的标准属性，且用于复选框组分组。

## id / name 属性命名规范

- **普通字段**：id="customer_name" name="customer_name"
  → 保存为 {"customer_name": "value"}
- **复选框组（多选）**：name="interests[]"（所有同组 checkbox 共用此 name）
  每个 checkbox 需要有唯一的 id，如 id="interests_tech"、id="interests_sports"
  → 保存为 {"interests[]": ["v1", "v2"]}
- **单选组**：name="gender"，每个 radio 有唯一 id
  → 保存为 {"gender": "male"}（以选中的 radio 的 value 为值，key 用 name）
- **动态表格**：id="items_0_name" name="items[0][name]"
  id="items_1_name" name="items[1][name]"
  → 保存为 {"items_0_name": "a", "items_1_name": "b"}
  行索引从 0 开始，JS 添加行时分配递增 id

## 内联 JS 模板 — 问卷核心逻辑（你必须包含在 HTML 中）

以下代码是问卷的「引擎」，你必须在 HTML 中包含以下逻辑（可以调整细节，但核心流程不可变）：
```
<script>
(function() {
  var cfg = window.__SURVEY_CONFIG__ || {};
  var token = cfg.surveyToken || '';
  var LS_KEY = 'survey_' + token;

  // ── 数据采集：所有带 name 属性控件 → 扁平 JSON ──
  function collectData() {
    var data = {}, seen = {};
    var els = document.querySelectorAll('[name]');
    for (var i = 0; i < els.length; i++) {
      var el = els[i];
      var nm = el.getAttribute('name');
      if (!nm) continue;
      if ((el.type === 'radio' || el.type === 'checkbox') && !el.checked) continue;
      if (el.type === 'checkbox' && /\[\]$/.test(nm)) {
        if (!seen[nm]) { data[nm] = []; seen[nm] = true; }
        data[nm].push(el.value);
      } else {
        var key = el.id || nm;
        data[key] = el.value;
      }
    }
    return data;
  }

  // ── 保存到本地（localStorage JSON）──
  function saveLocal() {
    try {
      var data = collectData();
      var list = JSON.parse(localStorage.getItem(LS_KEY) || '[]');
      list.push({ data: data, savedAt: new Date().toISOString() });
      localStorage.setItem(LS_KEY, JSON.stringify(list));
      showToast('已保存到本地 \u2713', 'success');
    } catch(e) { showToast('保存失败：' + e.message, 'error'); }
  }

  // ── 恢复最近一次本地保存 ──
  function restoreLast() {
    try {
      var list = JSON.parse(localStorage.getItem(LS_KEY) || '[]');
      if (list.length === 0) return;
      var record = list[list.length - 1];
      if (!record || !record.data) return;
      restoreData(record.data);
      showToast('已恢复上次保存 \u2713', 'success');
    } catch(e) {}
  }

  // ── 恢复数据到表单 ──
  function restoreData(data) {
    if (!data) return;
    // 复选框组
    for (var key in data) {
      if (!/\[\]$/.test(key)) continue;
      var vals = Array.isArray(data[key]) ? data[key] : [data[key]];
      var cbs = document.querySelectorAll('input[type="checkbox"][name="' + key + '"]');
      for (var ci = 0; ci < cbs.length; ci++) {
        cbs[ci].checked = vals.indexOf(cbs[ci].value) !== -1;
      }
    }
    // 单值字段：优先 id 查找，回退 name
    for (var key in data) {
      if (/\[\]$/.test(key)) continue;
      var v = data[key];
      var el = document.getElementById(key) || document.querySelector('[name="' + key + '"]');
      if (!el) continue;
      if (el.type === 'radio') {
        var rn = el.getAttribute('name');
        var radios = document.querySelectorAll('[name="' + rn + '"]');
        for (var ri = 0; ri < radios.length; ri++) {
          radios[ri].checked = (radios[ri].value === String(v));
        }
      } else if (el.type === 'checkbox') {
        el.checked = (v === true || v === 'true' || v === 'on' || v === '1');
      } else {
        el.value = v;
      }
    }
  }

  // ── 提交到服务器 ──
  function doSubmit() {
    var data = collectData();
    var payload = {
      survey_token: token,
      submitter_name: '',
      content: JSON.stringify(data),
      word_count: JSON.stringify(data).replace(/\\s/g, '').length,
      raw_data: data,
      save_type: 'submit'
    };
    fetch('/api/v1/survey/submit', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    }).then(function(r) { return r.json(); })
      .then(function(res) {
        showToast(res.code === 200 ? '提交成功 \u2713' : '提交失败：' + (res.msg || '未知错误'),
                 res.code === 200 ? 'success' : 'error');
        if (res.code === 200) {
          // 提交成功后清除本地保存
          localStorage.removeItem(LS_KEY);
        }
      })
      .catch(function(err) { showToast('提交失败：' + err.message, 'error'); });
  }

  // ── Toast 提示 ──
  function showToast(msg, type) {
    var colors = {
      success: 'background:#e6f7e6;color:#2e7d32;border:1px solid #a5d6a7;',
      error: 'background:#fdecea;color:#c62828;border:1px solid #ef9a9a;',
      info: 'background:#e3f2fd;color:#1565c0;border:1px solid #90caf9;'
    };
    var t = document.createElement('div');
    t.textContent = msg;
    t.style.cssText = 'position:fixed;top:20px;right:20px;z-index:99999;padding:12px 24px;border-radius:6px;font-size:14px;box-shadow:0 4px 12px rgba(0,0,0,0.15);animation:svFadeIn 0.3s ease;font-family:sans-serif;' + (colors[type] || colors.info);
    document.body.appendChild(t);
    setTimeout(function() { t.style.opacity = '0'; t.style.transition = 'opacity 0.3s'; setTimeout(function() { if (t.parentNode) t.parentNode.removeChild(t); }, 300); }, 2500);
  }

  // ── 绑定按钮 + 自动恢复 ──
  function bind() {
    document.addEventListener('click', function(e) {
      if (e.target.closest('.sv-save')) { e.preventDefault(); saveLocal(); }
      if (e.target.closest('.sv-submit')) { e.preventDefault(); doSubmit(); }
    });
    // 页面加载后，如果表单为空则尝试恢复本地保存
    var hasInput = false;
    var inputs = document.querySelectorAll('input[name], textarea[name], select[name]');
    for (var i = 0; i < inputs.length; i++) {
      var el = inputs[i];
      if (el.type === 'checkbox' || el.type === 'radio') {
        if (el.checked) { hasInput = true; break; }
      } else if (el.value && el.value.trim()) {
        hasInput = true; break;
      }
    }
    if (!hasInput) restoreLast();
  }

  // 添加 fadeIn 动画
  var style = document.createElement('style');
  style.textContent = '@keyframes svFadeIn{from{opacity:0;transform:translateY(-10px)}to{opacity:1;transform:translateY(0)}}';
  document.head.appendChild(style);

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', bind);
  else bind();
})();
</script>
```

**重要**：以上模板代码是问卷正常运行的最少必要逻辑，不可省略核心流程（collectData / saveLocal / restoreLast / doSubmit / bind）。你可以在此基础上扩展（如添加提交前验证、自定义 toast 样式），但不能删除这些核心函数。

## 数据格式

- 本地存储：localStorage key 为 `survey_{token}`，value 为 JSON 数组 `[{data:{...}, savedAt:"..."}, ...]`
- 提交到服务器：POST `/api/v1/survey/submit`，body 为 JSON
- 数据隔离：不同问卷的 token 不同，localStorage key 不同，天然隔离

## 样式设计自由

- CSS 完全由你自由设计：内联 <style> 标签或 style 属性
- 可以设计任何视觉风格：极简、卡通、商务、暗色模式、渐变、毛玻璃等

## 交互实现自由

- 可以自由编写额外的 <script> 标签和任意 JS 逻辑
- 动态表格、全选按钮、条件显示、输入验证、动画等，全部由你在 HTML 中用原生 JS 自由实现
- 唯一要求：交互的最终结果必须反映到带正确 id + name 属性的表单控件上

## 交互实现建议（非强制）

- 动态表格：用 insertRow / deleteRow 或 cloneNode 实现添加/删除行，行索引自行管理
- 复选框全选：用 querySelectorAll + forEach 实现切换
- 条件显示：用 onchange / onclick 事件控制 display/visibility
- 输入验证：在 doSubmit 前用自定义 JS 校验
- 字数统计：textarea 的 oninput 事件实时更新计数

## 注意事项

- 禁止在 <summary> 标签内放置交互式元素（button、input、select、a），
  这些元素在 <summary> 内无法正常工作。全选按钮等必须放在 <details> 内容区。
- 确保所有自定义 JS 在 DOMContentLoaded 之后执行或放在 </body> 之前。
- **不要引入任何外部 JS/CSS 文件**（不要使用 <link> 或外部 <script src>），全部内联。

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
            )

            _update_progress(task_id, "running", "generating", 87, "AI 生成完成，正在进行安全审核...")

            # ── 阶段 3: 安全审核 + 保存 (87-100%) ──
            from app.utils.survey_security import check_html_content
            security_result = check_html_content(html_content)
            _update_progress(task_id, "running", "saving", 90, "安全审核完成，正在保存文件...")

            os.makedirs(SURVEY_WEB_DIR, exist_ok=True)
            file_name = f"survey_{uuid.uuid4().hex[:12]}.html"
            file_path = os.path.join(SURVEY_WEB_DIR, file_name)

            short_token = self._gen_short_token()
            html_content = html_content.replace("__SURVEY_TOKEN__", short_token)

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
                    max_tokens=8192,
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
                # 追加 assistant 回复（使用原始内容保持历史准确）和 continue 指令
                messages.append({"role": "assistant", "content": raw_content})
                messages.append(
                    {"role": "user", "content": "直接从截断处继续输出HTML代码，不要输出任何解释、前言或代码围栏，只输出纯HTML片段。"}
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
