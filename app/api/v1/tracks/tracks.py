"""轨迹点数据 API 路由 — 车型/车辆查询、同步、清除、列表"""
from fastapi import APIRouter, Depends, Query

from app.controllers.track import track_controller
from app.core.ctx import CTX_USER_ID
from app.core.dependency import AuthControl
from app.schemas.base import Success, SuccessExtra
from app.schemas.tracks import TrackClearRequest, TrackSyncRequest

router = APIRouter()


@router.get("/accounts", summary="获取用户关联的像素账户列表")
async def get_user_accounts(
    current_user=Depends(AuthControl.is_authed),
):
    user_id = CTX_USER_ID.get()
    accounts = await track_controller.get_user_accounts(user_id)
    return Success(data=accounts)


@router.get("/car-types", summary="获取可用车型列表")
async def get_car_types(
    account_id: int = Query(..., description="像素账户ID"),
    current_user=Depends(AuthControl.is_authed),
):
    car_types = await track_controller.get_car_types(account_id)
    return Success(data=car_types)


@router.get("/cars", summary="获取车型下的车辆列表")
async def get_cars(
    account_id: int = Query(..., description="像素账户ID"),
    car_type: int = Query(..., description="车型类型"),
    current_user=Depends(AuthControl.is_authed),
):
    cars = await track_controller.get_cars(account_id, car_type)
    return Success(data=cars)


@router.post("/sync", summary="同步轨迹点数据")
async def sync_tracks(
    req: TrackSyncRequest,
    current_user=Depends(AuthControl.is_authed),
):
    user_id = CTX_USER_ID.get()
    result = await track_controller.sync(
        user_id=user_id,
        account_id=req.account_id,
        car_id=req.car_id,
        start_time=req.start_time.isoformat(),
        end_time=req.end_time.isoformat(),
    )
    return Success(data=result)


@router.post("/clear", summary="清除轨迹点数据")
async def clear_tracks(
    req: TrackClearRequest,
    current_user=Depends(AuthControl.is_authed),
):
    user_id = CTX_USER_ID.get()
    deleted_count = await track_controller.clear(user_id, req.account_id, req.car_id)
    return Success(data={"deleted": deleted_count})


@router.get("/list", summary="查看轨迹点数据列表")
async def list_tracks(
    page: int = Query(1, description="页码"),
    page_size: int = Query(10, description="每页数量"),
    account_id: int = Query(None, description="像素账户ID"),
    car_id: str = Query("", description="车辆ID搜索"),
    road_name: str = Query("", description="道路名称搜索"),
    current_user=Depends(AuthControl.is_authed),
):
    user_id = CTX_USER_ID.get()
    total, data = await track_controller.list_tracks(
        user_id=user_id,
        page=page,
        page_size=page_size,
        account_id=account_id,
        car_id=car_id,
        road_name=road_name,
    )
    return SuccessExtra(data=data, total=total, page=page, page_size=page_size)
