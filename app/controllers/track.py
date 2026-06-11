"""轨迹点数据 Controller — 车型/车辆查询、同步、清除、列表"""
from typing import List, Optional

import httpx
from tortoise.expressions import Q

from app.log import logger
from app.models.admin import Track, PixelAccount
from app.utils.pixel_api import get_pixel_token

# 像素平台 API 端点
CAR_TYPE_API = "https://road.xiangsu.work/bvr-gate/api/web/eventbefore/getCarType"
RENT_CAR_API = "https://road.xiangsu.work/bvr-gate/api/web/eventbefore/getRentCarByType"
TRACK_API_URL = "https://road.xiangsu.work/bvr-gate/api/web/eventbefore/getCarTrack"


class TrackController:
    """轨迹点数据控制器"""

    model = Track

    async def _get_token(self, account_id: int) -> str:
        """获取像素账户的 access token"""
        account = await PixelAccount.filter(id=account_id).first()
        if not account:
            raise ValueError(f"像素账户不存在: id={account_id}")
        token = await get_pixel_token(
            username=account.username,
            password=account.password,
            org=account.tenant_address,
        )
        if not token:
            raise ValueError("像素平台 token 获取失败，请检查账户配置")
        return token

    async def get_user_accounts(self, user_id: int) -> List[dict]:
        """获取用户关联的像素账户列表"""
        accounts = await PixelAccount.filter(users__id=user_id).all()
        return [{"id": a.id, "username": a.username, "tenant_address": a.tenant_address} for a in accounts]

    async def get_car_types(self, account_id: int) -> List[dict]:
        """获取指定账户的可用车型列表"""
        token = await self._get_token(account_id)
        headers = {"Authorization": f"Bearer {token}"}

        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(CAR_TYPE_API, headers=headers)

        if response.status_code != 200:
            raise ValueError(f"车型 API 请求失败: status={response.status_code}")

        data = response.json()
        if data.get("statusCode") != 200:
            raise ValueError(f"车型 API 返回错误: {data.get('message', 'unknown')}")

        car_types = data.get("data", [])
        return [
            {"id": ct["id"], "name": ct["name"], "type": ct["type"]}
            for ct in car_types
            if ct.get("deleteFlag") == 0
        ]

    async def get_cars(self, account_id: int, car_type: int) -> List[dict]:
        """获取指定账户和车型下的车辆列表"""
        token = await self._get_token(account_id)
        headers = {"Authorization": f"Bearer {token}"}
        params = {"carType": car_type}

        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(RENT_CAR_API, params=params, headers=headers)

        if response.status_code != 200:
            raise ValueError(f"车辆列表 API 请求失败: status={response.status_code}")

        data = response.json()
        if data.get("statusCode") != 200:
            raise ValueError(f"车辆列表 API 返回错误: {data.get('message', 'unknown')}")

        cars = data.get("data", [])
        return [
            {"id": c["id"], "car_id": c["carId"], "car_no": c.get("carNo", ""), "name": c.get("name", ""), "device_id": c.get("deviceId", "")}
            for c in cars
            if c.get("deleteFlag") == 0
        ]

    async def sync(self, user_id: int, account_id: int, car_id: str, start_time: str, end_time: str) -> dict:
        """同步轨迹点数据：调用像素平台 API 获取数据并 upsert"""
        token = await self._get_token(account_id)

        params = {
            "carId": car_id,
            "startCrtTime": f"{start_time} 00:00:00",
            "endCrtTime": f"{end_time} 23:59:59",
        }
        headers = {"Authorization": f"Bearer {token}"}

        async with httpx.AsyncClient(timeout=120) as client:
            response = await client.get(TRACK_API_URL, params=params, headers=headers)

        if response.status_code != 200:
            raise ValueError(f"轨迹数据 API 请求失败: status={response.status_code}")

        data = response.json()
        if data.get("statusCode") != 200:
            raise ValueError(f"轨迹数据 API 返回错误: {data.get('message', 'unknown')}")

        records = data.get("data", [])
        total_api = len(records)

        created = 0
        updated = 0

        for record in records:
            remote_id = record.get("id", "")
            existing = await Track.filter(
                remote_id=remote_id,
                pixel_account_id=account_id,
            ).first()

            track_data = {
                "remote_id": remote_id,
                "pixel_account_id": account_id,
                "car_id": record.get("carId", car_id),
                "road_name": record.get("roadName"),
                "car_type": record.get("carType"),
                "longitude": record.get("longitude"),
                "latitude": record.get("latitude"),
                "flag": record.get("flag"),
                "track_time": record.get("trackTime"),
                "extra_data": record,
            }

            if existing:
                await existing.update_from_dict(track_data).save()
                updated += 1
            else:
                await Track.create(**track_data)
                created += 1

        logger.info(
            f"轨迹数据同步完成: account_id={account_id}, car_id={car_id}, "
            f"api_total={total_api}, created={created}, updated={updated}"
        )

        return {"created": created, "updated": updated, "total_api": total_api}

    async def clear(self, user_id: int, account_id: int, car_id: str = "") -> int:
        """清除指定账户（或指定车辆）的轨迹点数据"""
        q = Q(pixel_account_id=account_id)
        if car_id:
            q &= Q(car_id=car_id)
        count = await Track.filter(q).count()
        await Track.filter(q).delete()
        logger.info(f"轨迹数据清除完成: account_id={account_id}, car_id={car_id or 'ALL'}, deleted={count}")
        return count

    async def list_tracks(
        self,
        user_id: int,
        page: int = 1,
        page_size: int = 10,
        account_id: Optional[int] = None,
        car_id: Optional[str] = None,
        road_name: Optional[str] = None,
    ):
        """分页查询轨迹点数据，仅显示当前用户有权限的像素账户数据"""
        q = Q()

        user_accounts = await PixelAccount.filter(users__id=user_id).values_list("id", flat=True)
        if not user_accounts:
            return 0, []
        q &= Q(pixel_account_id__in=list(user_accounts))

        if account_id:
            q &= Q(pixel_account_id=account_id)
        if car_id:
            q &= Q(car_id__contains=car_id)
        if road_name:
            q &= Q(road_name__contains=road_name)

        total = await Track.filter(q).count()
        objs = await Track.filter(q).offset((page - 1) * page_size).limit(page_size).order_by("-track_time")

        data = []
        for obj in objs:
            d = {
                "id": obj.id,
                "remote_id": obj.remote_id,
                "pixel_account_id": obj.pixel_account_id,
                "car_id": obj.car_id,
                "road_name": obj.road_name,
                "car_type": obj.car_type,
                "longitude": obj.longitude,
                "latitude": obj.latitude,
                "flag": obj.flag,
                "track_time": obj.track_time.isoformat() if obj.track_time else None,
                "created_at": obj.created_at.isoformat() if obj.created_at else None,
            }
            data.append(d)

        return total, data


track_controller = TrackController()
