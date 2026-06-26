"""调研问卷 Controller"""
import asyncio
import json
import os
import secrets
import uuid
from typing import List, Optional, Tuple

from tortoise.expressions import Q

from app.core.crud import CRUDBase
from app.log import logger
from app.models.admin import AIProxy, Skill, Survey, SurveySubmission, User
from app.schemas.survey import SurveyCreate, SurveySubmissionCreate, SurveyUpdate
from app.settings.config import settings

# 问卷网页文件存放目录
SURVEY_WEB_DIR = os.path.join(settings.BASE_DIR, "uploads", "static_web")
SURVEY_LIB_URL = "/api/v1/survey/static/survey-lib.js"
SURVEY_CSS_URL = "/api/v1/survey/static/survey-lib.css"

# AI 生成问卷网页的 System Prompt
AI_SURVEY_SYSTEM_PROMPT = """你是一个专业的前端开发者，负责创建用户调查问卷网页。

## 要求
1. 只输出完整的 HTML 文件（从 <!DOCTYPE html> 开始）
2. 必须引用以下 CSS/JS 库：
   - CSS: /api/v1/survey/static/survey-lib.css
   - JS: /api/v1/survey/static/survey-lib.js
3. 页面中必须使用 survey-lib.css 的 CSS 类名（sv-*）来构建表单控件
4. 在页面底部必须有两个按钮："保存草稿"（class="sv-save sv-btn sv-btn-default"）和"提交问卷"（class="sv-submit sv-btn sv-btn-primary"）
5. 使用 window.__SURVEY_CONFIG__ 配置 SurveyLib，包含 surveyToken（用占位符 __SURVEY_TOKEN__）
6. 表单控件使用标准 HTML 元素：input, select, textarea，并始终设置 name 属性
7. 所有控件必须使用 sv-input, sv-select, sv-textarea, sv-radio-group, sv-checkbox-group 等 CSS 类
8. 绝对禁止包含任何 <script> 标签（除了引用 survey-lib.js 的那个）
9. 绝对禁止使用 eval、fetch、XMLHttpRequest、innerHTML、onclick 等 JS 代码
10. 绝对禁止文件读写或网络请求代码

## CSS 类速查
- 容器：sv-container
- 标题：sv-title / sv-subtitle
- 段落：sv-section / sv-section-title
- 行/列：sv-row / sv-col / sv-col-full
- 标签：sv-label / sv-required
- 输入框：sv-input
- 下拉框：sv-select
- 文本域：sv-textarea
- 单选组：sv-radio-group / sv-radio
- 多选组：sv-checkbox-group / sv-checkbox
- 评分：sv-rating
- 开关：sv-switch / sv-switch-slider
- 按钮：sv-btn / sv-btn-primary / sv-btn-default / sv-btn-success / sv-btn-lg / sv-btn-block
- 按钮组：sv-btn-group
- 提示：sv-hint

## 示例输出结构
<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>问卷标题</title>
  <link rel="stylesheet" href="/api/v1/survey/static/survey-lib.css">
</head>
<body>
  <div class="sv-container">
    <h1 class="sv-title">问卷标题</h1>
    <p class="sv-subtitle">描述信息</p>
    <!-- 表单内容 -->
    <div class="sv-btn-group">
      <button type="button" class="sv-save sv-btn sv-btn-default">保存草稿</button>
      <button type="button" class="sv-submit sv-btn sv-btn-primary">提交问卷</button>
    </div>
  </div>
  <script>
    window.__SURVEY_CONFIG__ = { surveyToken: '__SURVEY_TOKEN__' };
  </script>
  <script src="/api/v1/survey/static/survey-lib.js"></script>
</body>
</html>"""


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

    # ── AI 创建问卷 ──
    async def create_with_ai(self, obj_in: SurveyCreate, creator_id: int) -> dict:
        """通过 AI 生成问卷网页，经安全审核后保存"""
        # 1. 获取 AI 代理配置
        proxy = await AIProxy.filter(id=obj_in.ai_proxy_id).first()
        if not proxy:
            raise ValueError("AI代理不存在")
        if not proxy.url or not proxy.token:
            raise ValueError("AI代理配置不完整，请检查 URL 和 Token")

        # 2. 获取 Skill 内容作为系统提示词补充
        skill_content = ""
        if obj_in.skill_id:
            skill = await Skill.filter(id=obj_in.skill_id).first()
            if skill:
                skill_content = f"\n\n## 以下为参考技能内容：\n{skill.content}"

        # 3. 构建 AI 请求
        system_prompt = AI_SURVEY_SYSTEM_PROMPT + skill_content
        user_prompt = obj_in.prompt

        # 4. 调用 AI API
        html_content = await self._call_ai_api(
            url=proxy.url,
            token=proxy.token,
            model=proxy.model or "deepseek-chat",
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )

        # 5. 安全审核
        from app.utils.survey_security import check_html_content
        security_result = check_html_content(html_content)

        # 6. 保存文件（不管是否通过审核都先保存，审核不通过的文件不提供短链接）
        os.makedirs(SURVEY_WEB_DIR, exist_ok=True)
        file_name = f"survey_{uuid.uuid4().hex[:12]}.html"
        file_path = os.path.join(SURVEY_WEB_DIR, file_name)

        # 替换占位符为实际 token
        short_token = self._gen_short_token()
        html_content = html_content.replace("__SURVEY_TOKEN__", short_token)

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(html_content)

        file_size = os.path.getsize(file_path)

        # 7. 创建数据库记录
        security_log_json = json.dumps(security_result, ensure_ascii=False)
        survey = await self.model.create(
            name=obj_in.name,
            file_name=file_name,
            file_path=file_path,
            file_size=file_size,
            ai_proxy_id=obj_in.ai_proxy_id,
            skill_id=obj_in.skill_id,
            prompt=obj_in.prompt,
            short_url_token=short_token if security_result["passed"] else None,
            is_valid=security_result["passed"],
            security_log=security_log_json,
            creator_id=creator_id,
        )

        # 8. 设置授权用户
        if obj_in.user_ids:
            await self.update_users(survey, obj_in.user_ids)

        # 9. 返回结果
        result = self._to_output(survey)
        result["security"] = security_result

        if not security_result["passed"]:
            result["message"] = "问卷网页已生成但安全审核未通过，短链接已禁用。请检查 Prompt 并重新创建。"

        return result

    # ── 调用 AI API ──
    async def _call_ai_api(
        self, url: str, token: str, model: str,
        system_prompt: str, user_prompt: str,
    ) -> str:
        """使用 OpenAI SDK 调用 AI API 生成 HTML"""
        from openai import AsyncOpenAI

        # 构造 base_url（需包含 /v1 路径）
        base_url = url.rstrip("/")
        if not base_url.endswith("/v1"):
            base_url += "/v1"

        client = AsyncOpenAI(
            base_url=base_url,
            api_key=token,
            timeout=180.0,
            max_retries=2,
        )

        try:
            # extra_body 关闭 thinking 模式，确保 content 字段有内容
            response = await client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.7,
                max_tokens=8192,
                extra_body={"thinking": {"type": "disabled"}},
            )
            choice = response.choices[0]
            content = choice.message.content or ""
            logger.info(f"AI 响应长度: content={len(content)}, model={model}")

            if not content:
                logger.error(f"AI 返回空内容，完整响应: {response}")
                raise ValueError("AI 返回了空内容，请检查模型配置")

            # 提取 HTML 内容
            html = self._extract_html(content)
            if not html.strip().startswith("<"):
                logger.error(f"提取后内容不以 < 开头: {html[:200]}")
                raise ValueError(f"AI 生成内容不是 HTML 格式")
            return html
        except Exception as e:
            logger.exception(f"AI API 调用异常: {e}")
            raise ValueError(f"AI API 调用失败: {str(e)}")

    @staticmethod
    def _extract_html(content: str) -> str:
        """从 AI 响应中提取 HTML 内容"""
        content = content.strip()

        # 如果包含 markdown 代码块，提取其中内容
        if "```html" in content:
            start = content.index("```html") + 7
            end = content.rindex("```")
            content = content[start:end].strip()
        elif "```" in content:
            start = content.index("```") + 3
            end = content.rindex("```")
            content = content[start:end].strip()

        # 如果不以 <!DOCTYPE 或 <html 开头，尝试找到开头
        if not content.lower().startswith(("<!doctype", "<html")):
            lower = content.lower()
            for tag in ("<!doctype html>", "<html>", "<html "):
                idx = lower.find(tag)
                if idx >= 0:
                    content = content[idx:]
                    break

        return content

    # ── 更新问卷 ──
    async def update_survey(self, survey_id: int, obj_in: SurveyUpdate) -> Optional[dict]:
        survey = await self.model.filter(id=survey_id).first()
        if not survey:
            return None
        if obj_in.name is not None:
            survey.name = obj_in.name
            await survey.save()
        if obj_in.user_ids is not None:
            await self.update_users(survey, obj_in.user_ids)
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
        """提交问卷数据"""
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
