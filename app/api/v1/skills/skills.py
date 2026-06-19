import logging

from urllib.parse import quote

from fastapi import APIRouter, Query
from fastapi.responses import Response
from tortoise.expressions import Q

from app.controllers.skill import skill_controller
from app.core.ctx import CTX_USER_ID
from app.schemas.base import Fail, Success, SuccessExtra
from app.schemas.skills import *  # noqa: F403

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/list", summary="查看技能列表")
async def list_skills(
    page: int = Query(1, description="页码"),
    page_size: int = Query(10, description="每页数量"),
):
    user_id = CTX_USER_ID.get()
    total, skill_objs = await skill_controller.get_accessible_skills(
        user_id=user_id, page=page, page_size=page_size
    )
    data = []
    for obj in skill_objs:
        obj_dict = await obj.to_dict(m2m=True)
        data.append(obj_dict)
    return SuccessExtra(data=data, total=total, page=page, page_size=page_size)


@router.get("/get", summary="查看技能")
async def get_skill(
    skill_id: int = Query(..., description="技能ID"),
):
    user_id = CTX_USER_ID.get()
    skill = await skill_controller.check_permission(skill_id=skill_id, user_id=user_id)
    if not skill:
        return Fail(code=403, msg="无权访问该技能")
    skill_dict = await skill.to_dict(m2m=True)
    return Success(data=skill_dict)


@router.post("/create", summary="创建技能")
async def create_skill(skill_in: SkillCreate):
    user_id = CTX_USER_ID.get()
    obj_dict = skill_in.create_dict()
    obj_dict["content"] = skill_in.content
    skill = await skill_controller.create(obj_in=obj_dict)
    # 默认添加创建者为可访问用户
    all_user_ids = set(skill_in.user_ids)
    all_user_ids.add(user_id)
    await skill_controller.update_users(skill, list(all_user_ids))
    return Success(msg="创建成功")


@router.post("/ai-create", summary="AI创建技能")
async def ai_create_skill(skill_in: SkillAICreate):
    import asyncio

    from openai import OpenAI

    from app.models.admin import AIProxy

    user_id = CTX_USER_ID.get()

    # 1. 获取 AI 代理
    ai_proxy = await AIProxy.filter(name=skill_in.proxy_name).first()
    if not ai_proxy:
        return Fail(code=404, msg="AI代理不存在")

    # 2. 权限检查
    from app.controllers.ai_proxy import ai_proxy_controller
    has_proxy_permission = await ai_proxy_controller.check_permission_by_name(
        name=skill_in.proxy_name, user_id=user_id
    )
    if not has_proxy_permission:
        return Fail(code=403, msg="无权使用该AI代理")

    # 3. 获取参考技能内容（可选）
    source_content = ""
    if skill_in.source_skill_id:
        source_skill = await skill_controller.check_permission(
            skill_id=skill_in.source_skill_id, user_id=user_id
        )
        if not source_skill:
            return Fail(code=403, msg="无权访问参考技能")
        source_content = source_skill.content

    # 4. 构建 system prompt
    system_prompt = (
        "你是一个技能文档生成助手。根据用户的需求描述，生成一个结构化的技能文档。\n\n"
        "要求：\n"
        "1. 输出格式为严格的 JSON，包含 \"title\" 和 \"content\" 两个字段\n"
        "2. title 是技能标题（简洁明了，不超过 100 字）\n"
        "3. content 是 Markdown 格式的技能内容，包含清晰的章节结构（## 标题）\n"
        "4. 不要输出任何 JSON 之外的文字\n"
    )
    if source_content:
        system_prompt += (
            f"\n## 参考技能内容\n{source_content}\n\n"
            "请在参考上述技能风格的基础上，结合用户需求进行再创作。"
        )

    # 5. 调用 AI
    client = OpenAI(base_url=ai_proxy.url, api_key=ai_proxy.token)
    model = ai_proxy.model or "gpt-3.5-turbo"

    def _sync_call():
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": skill_in.prompt},
            ],
            temperature=0.7,
        )
        return response.choices[0].message.content

    ai_response = await asyncio.to_thread(_sync_call)

    logger.info(f"AI原始响应(前500字): {ai_response[:500]}")

    # 6. 解析 AI 响应 — 多策略 JSON 提取
    result = _extract_skill_json(ai_response)
    if result is None:
        logger.warning(f"AI响应JSON解析全部失败，完整响应: {ai_response}")
        return Fail(code=500, msg="AI生成内容格式异常，请重试")

    title = result.get("title", "").strip()
    content = result.get("content", "").strip()
    if not title:
        return Fail(code=500, msg="AI未能生成有效标题")

    # 7. 创建技能
    obj_dict = {"title": title, "content": content}
    skill = await skill_controller.create(obj_in=obj_dict)
    all_user_ids = set(skill_in.user_ids)
    all_user_ids.add(user_id)
    await skill_controller.update_users(skill, list(all_user_ids))

    skill_dict = await skill.to_dict(m2m=True)
    return Success(data=skill_dict, msg="AI创建成功")


@router.post("/update", summary="更新技能")
async def update_skill(skill_in: SkillUpdate):
    user_id = CTX_USER_ID.get()
    skill = await skill_controller.check_permission(skill_id=skill_in.id, user_id=user_id)
    if not skill:
        return Fail(code=403, msg="无权修改该技能")
    await skill_controller.update(id=skill_in.id, obj_in=skill_in)
    await skill_controller.update_users(skill, skill_in.user_ids)
    return Success(msg="更新成功")


@router.delete("/delete", summary="删除技能")
async def delete_skill(
    skill_id: int = Query(..., description="技能ID"),
):
    user_id = CTX_USER_ID.get()
    skill = await skill_controller.check_permission(skill_id=skill_id, user_id=user_id)
    if not skill:
        return Fail(code=403, msg="无权删除该技能")
    await skill_controller.remove(id=skill_id)
    return Success(msg="删除成功")


@router.get("/export", summary="导出技能")
async def export_skill(
    skill_id: int = Query(..., description="技能ID"),
):
    user_id = CTX_USER_ID.get()
    skill = await skill_controller.check_permission(skill_id=skill_id, user_id=user_id)
    if not skill:
        return Fail(code=403, msg="无权导出该技能")
    body = f"# {skill.title}\n\n{skill.content}".encode("utf-8")
    filename = f"{skill.title}.md"
    encoded_filename = quote(filename)
    return Response(
        content=body,
        media_type="text/markdown; charset=utf-8",
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}",
        },
    )


@router.get("/users", summary="获取用户列表（用于权限选择）")
async def get_users_for_select():
    """返回所有活跃用户，用于 Skill 的权限选择器"""
    from app.models.admin import User
    users = await User.filter(is_active=True).all()
    data = [{"id": u.id, "username": u.username, "alias": u.alias} for u in users]
    return Success(data=data)


# ── AI 响应 JSON 解析辅助函数 ──

def _extract_skill_json(text: str) -> dict | None:
    """多策略提取 AI 响应中的 {title, content} JSON 对象。

    策略（按顺序尝试）：
    1. 匹配 ```json ... ``` 代码块
    2. 匹配 ``` ... ``` 代码块（无语言标记）
    3. 从第一个 { 匹配到最后一个 } 提取最外层 JSON 对象
    4. 用 json5 宽松解析（如果已安装）
    5. 回退：将整个文本作为 content，自动生成 title
    """
    import json
    import re

    strategies = []

    # 策略1: ```json ... ```
    m = re.search(r"```json\s*([\s\S]*?)\s*```", text, re.IGNORECASE)
    if m:
        strategies.append(("json-codeblock", m.group(1).strip()))

    # 策略2: ``` ... ```
    m = re.search(r"```\s*([\s\S]*?)\s*```", text)
    if m:
        strategies.append(("codeblock", m.group(1).strip()))

    # 策略3: 从 { 到 } 提取最外层 JSON
    first_brace = text.find("{")
    last_brace = text.rfind("}")
    if first_brace >= 0 and last_brace > first_brace:
        strategies.append(("brace-range", text[first_brace:last_brace + 1].strip()))

    # 策略4: 原始文本（去首尾空白）
    strategies.append(("raw", text.strip()))

    # 对每个候选尝试 json.loads
    json_decode_errors = []
    for name, candidate in strategies:
        try:
            result = json.loads(candidate)
            if isinstance(result, dict) and "title" in result:
                return result
        except (json.JSONDecodeError, ValueError) as e:
            json_decode_errors.append(f"{name}: {e}")

    # 策略5: 尝试 json5 宽松解析
    try:
        import json5
        for name, candidate in strategies:
            try:
                result = json5.loads(candidate)
                if isinstance(result, dict) and "title" in result:
                    return result
            except Exception:
                pass
    except ImportError:
        pass

    # 策略6: 回退 — 尝试修复常见 JSON 问题
    # 例如 AI 在 JSON 字符串内嵌入了未转义的双引号
    for name, candidate in strategies:
        try:
            fixed = _repair_json(candidate)
            if fixed != candidate:
                result = json.loads(fixed)
                if isinstance(result, dict) and "title" in result:
                    return result
        except (json.JSONDecodeError, ValueError):
            pass

    return None


def _repair_json(text: str) -> str:
    """尝试修复常见的 AI 生成 JSON 格式问题。"""
    import re

    s = text.strip()
    # 移除尾部多余的逗号（在 ] 或 } 之前）
    s = re.sub(r",(\s*[}\]])", r"\1", s)
    # 尝试用双反斜杠替换内容中的未转义反斜杠
    # （保守修复，避免过度修改）
    return s
