from fastapi import APIRouter, Query
from tortoise.expressions import Q

from app.controllers.pixel_account import pixel_account_controller
from app.schemas.base import Success, SuccessExtra
from app.schemas.pixel_accounts import *

router = APIRouter()


@router.get("/list", summary="查看像素账户列表")
async def list_pixel_account(
    page: int = Query(1, description="页码"),
    page_size: int = Query(10, description="每页数量"),
    username: str = Query("", description="用户名搜索"),
    tenant_address: str = Query("", description="租户地址搜索"),
):
    q = Q()
    if username:
        q &= Q(username__contains=username)
    if tenant_address:
        q &= Q(tenant_address__contains=tenant_address)
    total, objs = await pixel_account_controller.list(page=page, page_size=page_size, search=q)
    data = [await obj.to_dict(m2m=True, exclude_fields=["password"]) for obj in objs]
    return SuccessExtra(data=data, total=total, page=page, page_size=page_size)


@router.get("/get", summary="查看像素账户")
async def get_pixel_account(
    account_id: int = Query(..., description="像素账户ID"),
):
    obj = await pixel_account_controller.get(id=account_id)
    data = await obj.to_dict(m2m=True, exclude_fields=["password"])
    return Success(data=data)


@router.post("/create", summary="创建像素账户")
async def create_pixel_account(
    obj_in: PixelAccountCreate,
):
    await pixel_account_controller.create_account(obj_in=obj_in)
    return Success(msg="Created Successfully")


@router.post("/update", summary="更新像素账户")
async def update_pixel_account(
    obj_in: PixelAccountUpdate,
):
    await pixel_account_controller.update_account(obj_in=obj_in)
    return Success(msg="Updated Successfully")


@router.delete("/delete", summary="删除像素账户")
async def delete_pixel_account(
    account_id: int = Query(..., description="像素账户ID"),
):
    await pixel_account_controller.remove(id=account_id)
    return Success(msg="Deleted Successfully")
