"""调研问卷 Controller"""
import asyncio
import json
import os
import re
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

## 核心要求（必须遵守，否则问卷无法正常工作）
1. 只输出完整的 HTML 文件（从 <!DOCTYPE html> 开始）
2. 必须引入 SurveyLib JS 库：<script src="/api/v1/survey/static/survey-lib.js"></script>
3. 在页面底部必须有两个按钮，class 必须精确为：
   - "保存草稿"按钮：class="sv-save"
   - "提交问卷"按钮：class="sv-submit"
   （SurveyLib 通过这两个 class 绑定点击事件，不可改名）
4. 在 <script src="survey-lib.js"> 之前必须配置：
   <script>
     window.__SURVEY_CONFIG__ = { surveyToken: '__SURVEY_TOKEN__' };
   </script>
   （SurveyLib 自动读取此配置初始化，占位符 __SURVEY_TOKEN__ 会被后端替换为真实 token）
5. 所有表单控件（input、select、textarea）必须设置 name 属性
   （SurveyLib 通过 name 属性收集和恢复表单数据）
6. 样式可完全自由设计，不强制使用任何特定 CSS 类名或样式库
7. 可以包含自定义 <script> 标签和任意 JS 交互逻辑

## SurveyLib 提供的功能（通过 sv-save 和 sv-submit 按钮自动触发）
- collectFormData()：收集所有带 name 的表单数据
- toMarkdownTable()：将数据转为 Markdown 表格
- saveToLocal()：保存草稿到浏览器 localStorage
- restore(data) / restoreLastSave()：从 localStorage 恢复表单数据
- submit()：提交问卷到服务器

## 示例输出结构
<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>问卷标题</title>
</head>
<body>
  <h1>问卷标题</h1>
  <p>描述信息</p>

  <label>姓名：<input type="text" name="name"></label>

  <fieldset>
    <legend>性别</legend>
    <label><input type="radio" name="gender" value="male"> 男</label>
    <label><input type="radio" name="gender" value="female"> 女</label>
  </fieldset>

  <label><input type="checkbox" name="agree" value="yes"> 我同意条款</label>

  <button type="button" class="sv-save">保存草稿</button>
  <button type="button" class="sv-submit">提交问卷</button>

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

        # 5. 风险评估（不拦截，仅记录）
        from app.utils.survey_security import check_html_content
        security_result = check_html_content(html_content)

        # 6. 保存文件（始终提供短链接）
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
            short_url_token=short_token,
            is_valid=True,
            security_log=security_log_json,
            creator_id=creator_id,
        )

        # 8. 关联授权用户
        if obj_in.user_ids:
            await self.update_users(survey, obj_in.user_ids)

        # 9. 返回结果
        result = self._to_output(survey)
        result["security"] = security_result

        risk_count = len(security_result.get("issues", []))
        if risk_count:
            result["message"] = f"问卷已生成，检测到 {risk_count} 条风险信息（未拦截）。"

        return result

    async def _call_ai_api(
        self,
        url: str,
        token: str,
        model: str,
        system_prompt: str,
        user_prompt: str,
    ) -> str:
        """调用 AI API 生成问卷网页（使用 openai SDK）"""
        from openai import OpenAI

        client = OpenAI(base_url=url, api_key=token)

        def _sync_call():
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.7,
                max_tokens=8192,
            )
            content = response.choices[0].message.content
            if not content:
                raise ValueError("AI 返回内容为空")
            return content

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
