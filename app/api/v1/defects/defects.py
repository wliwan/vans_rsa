"""病害数据 API 路由 — 同步、清除、查询"""
from fastapi import APIRouter, Depends, Query

from app.controllers.defect import defect_controller
from app.core.ctx import CTX_USER_ID
from app.core.dependency import AuthControl
from app.schemas.base import Success, SuccessExtra
from app.schemas.defects import DefectClearRequest, DefectSyncRequest

router = APIRouter()


@router.get("/accounts", summary="获取用户关联的像素账户列表")
async def get_user_accounts(
    current_user=Depends(AuthControl.is_authed),
):
    """获取当前登录用户关联的像素账户（用于下拉选择）"""
    user_id = CTX_USER_ID.get()
    accounts = await defect_controller.get_user_accounts(user_id)
    return Success(data=accounts)


@router.post("/sync", summary="同步病害数据")
async def sync_defects(
    req: DefectSyncRequest,
    current_user=Depends(AuthControl.is_authed),
):
    """同步指定像素账户和时间段的病害数据"""
    user_id = CTX_USER_ID.get()
    result = await defect_controller.sync(
        user_id=user_id,
        account_id=req.account_id,
        start_time=req.start_time.isoformat(),
        end_time=req.end_time.isoformat(),
    )
    return Success(data=result)


@router.post("/clear", summary="清除病害数据")
async def clear_defects(
    req: DefectClearRequest,
    current_user=Depends(AuthControl.is_authed),
):
    """清除指定像素账户的全部病害数据"""
    user_id = CTX_USER_ID.get()
    deleted_count = await defect_controller.clear(user_id, req.account_id)
    return Success(data={"deleted": deleted_count})


@router.get("/list", summary="查看病害数据列表")
async def list_defects(
    page: int = Query(1, description="页码"),
    page_size: int = Query(10, description="每页数量"),
    account_id: int = Query(None, description="像素账户ID"),
    road_name: str = Query("", description="道路名称搜索"),
    risk_level_name: str = Query("", description="风险等级搜索"),
    status_name: str = Query("", description="状态搜索"),
    current_user=Depends(AuthControl.is_authed),
):
    """分页查询病害数据，仅显示当前用户有权限的像素账户数据"""
    user_id = CTX_USER_ID.get()
    total, data = await defect_controller.list_defects(
        user_id=user_id,
        page=page,
        page_size=page_size,
        account_id=account_id,
        road_name=road_name,
        risk_level_name=risk_level_name,
        status_name=status_name,
    )
    return SuccessExtra(data=data, total=total, page=page, page_size=page_size)
