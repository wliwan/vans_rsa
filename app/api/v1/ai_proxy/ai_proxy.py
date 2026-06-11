import logging

from fastapi import APIRouter, Query

from app.controllers.ai_proxy import ai_proxy_controller
from app.core.ctx import CTX_USER_ID
from app.schemas.ai_proxy import *
from app.schemas.base import Fail, Success, SuccessExtra

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/list", summary="查看AI代理列表")
async def list_proxies(
    page: int = Query(1, description="页码"),
    page_size: int = Query(10, description="每页数量"),
):
    user_id = CTX_USER_ID.get()
    total, objs = await ai_proxy_controller.get_accessible(user_id=user_id, page=page, page_size=page_size)
    data = [await obj.to_dict(m2m=True) for obj in objs]
    return SuccessExtra(data=data, total=total, page=page, page_size=page_size)


@router.get("/get", summary="查看AI代理")
async def get_proxy(proxy_id: int = Query(..., description="代理ID")):
    user_id = CTX_USER_ID.get()
    proxy = await ai_proxy_controller.check_permission(proxy_id=proxy_id, user_id=user_id)
    if not proxy:
        return Fail(code=403, msg="无权访问该代理")
    return Success(data=await proxy.to_dict(m2m=True))


@router.post("/create", summary="创建AI代理")
async def create_proxy(proxy_in: AIProxyCreate):
    user_id = CTX_USER_ID.get()
    obj_dict = proxy_in.create_dict()
    proxy = await ai_proxy_controller.create(obj_in=obj_dict)
    all_user_ids = set(proxy_in.user_ids)
    all_user_ids.add(user_id)
    await ai_proxy_controller.update_users(proxy, list(all_user_ids))
    return Success(msg="创建成功")


@router.post("/update", summary="更新AI代理")
async def update_proxy(proxy_in: AIProxyUpdate):
    user_id = CTX_USER_ID.get()
    proxy = await ai_proxy_controller.check_permission(proxy_id=proxy_in.id, user_id=user_id)
    if not proxy:
        return Fail(code=403, msg="无权修改该代理")
    await ai_proxy_controller.update(id=proxy_in.id, obj_in=proxy_in)
    await ai_proxy_controller.update_users(proxy, proxy_in.user_ids)
    return Success(msg="更新成功")


@router.delete("/delete", summary="删除AI代理")
async def delete_proxy(proxy_id: int = Query(..., description="代理ID")):
    user_id = CTX_USER_ID.get()
    proxy = await ai_proxy_controller.check_permission(proxy_id=proxy_id, user_id=user_id)
    if not proxy:
        return Fail(code=403, msg="无权删除该代理")
    await ai_proxy_controller.remove(id=proxy_id)
    return Success(msg="删除成功")


@router.get("/users", summary="获取用户列表（权限选择）")
async def get_users_for_select():
    from app.models.admin import User
    users = await User.filter(is_active=True).all()
    data = [{"id": u.id, "username": u.username, "alias": u.alias} for u in users]
    return Success(data=data)
