"""车辆状态检测 API 路由 — 账户选择、在线状态、设备信息"""
from fastapi import APIRouter, Depends, Query

from app.controllers.vehicle import vehicle_controller
from app.core.ctx import CTX_USER_ID
from app.core.dependency import AuthControl
from app.schemas.base import Success

router = APIRouter()


@router.get("/accounts", summary="获取用户关联的像素账户列表")
async def get_accounts(
    current_user=Depends(AuthControl.is_authed),
):
    user_id = CTX_USER_ID.get()
    accounts = await vehicle_controller.get_user_accounts(user_id)
    return Success(data=accounts)


@router.get("/car-types", summary="获取可用车型列表")
async def get_car_types(
    account_id: int = Query(..., description="像素账户ID"),
    current_user=Depends(AuthControl.is_authed),
):
    car_types = await vehicle_controller.get_car_types(account_id)
    return Success(data=car_types)


@router.get("/cars", summary="获取车型下的车辆列表")
async def get_cars(
    account_id: int = Query(..., description="像素账户ID"),
    car_type: int = Query(..., description="车型类型"),
    current_user=Depends(AuthControl.is_authed),
):
    cars = await vehicle_controller.get_cars(account_id, car_type)
    return Success(data=cars)


@router.get("/status", summary="检测车辆设备在线状态")
async def check_status(
    car_id: str = Query(..., description="车辆ID"),
    current_user=Depends(AuthControl.is_authed),
):
    result = await vehicle_controller.check_status(car_id)
    return Success(data=result)


@router.get("/device-info", summary="获取车辆设备完整信息")
async def device_info(
    car_id: str = Query(..., description="车辆ID"),
    current_user=Depends(AuthControl.is_authed),
):
    result = await vehicle_controller.get_info(car_id)
    return Success(data=result)


@router.get("/full-check", summary="一站式检测：在线状态+设备信息")
async def full_check(
    car_id: str = Query(..., description="车辆ID"),
    current_user=Depends(AuthControl.is_authed),
):
    result = await vehicle_controller.full_check(car_id)
    return Success(data=result)


@router.get("/refresh", summary="刷新设备在线状态")
async def refresh_status(
    car_id: str = Query(..., description="车辆ID"),
    current_user=Depends(AuthControl.is_authed),
):
    result = await vehicle_controller.refresh_status(car_id)
    return Success(data=result)


@router.get("/flow", summary="查询设备数据流量使用情况（含自动刷新设备信息）")
async def query_flow(
    car_id: str = Query(..., description="车辆ID"),
    date: str = Query(..., description="查询日期 (YYYY-MM-DD)"),
    current_user=Depends(AuthControl.is_authed),
):
    result = await vehicle_controller.query_flow(car_id, date)
    return Success(data=result)
