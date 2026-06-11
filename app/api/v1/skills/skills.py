import logging

from urllib.parse import quote

from fastapi import APIRouter, Query
from fastapi.responses import Response
from tortoise.expressions import Q

from app.controllers.skill import skill_controller
from app.core.ctx import CTX_USER_ID
from app.schemas.base import Fail, Success, SuccessExtra
from app.schemas.skills import *

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
