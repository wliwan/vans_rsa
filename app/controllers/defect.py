"""病害数据 Controller — 同步、清除、查询"""
import json
from typing import List, Optional

import httpx
from tortoise.expressions import Q

from app.core.crud import CRUDBase
from app.log import logger
from app.models.admin import Defect, PixelAccount
from app.utils.pixel_api import get_pixel_token

# 病害数据查询 API
DEFECT_API_URL = "https://road.xiangsu.work/bvr-gate/api/web/report/upRiskMangePage"


class DefectController:
    """病害数据控制器（不继承 CRUDBase，因为 Defect 没有 Create/Update Schema）"""

    model = Defect

    async def get_user_accounts(self, user_id: int) -> List[dict]:
        """获取用户关联的像素账户列表（用于下拉选择）"""
        accounts = await PixelAccount.filter(users__id=user_id).values("id", "username", "tenant_address")
        return list(accounts)
        

    async def sync(self, user_id: int, account_id: int, start_time: str, end_time: str) -> dict:
        """
        同步病害数据：调用像素平台 API 获取数据并存入本地。

        Args:
            user_id: 当前用户ID
            account_id: 像素账户ID
            start_time: 开始日期 (YYYY-MM-DD)
            end_time: 结束日期 (YYYY-MM-DD)

        Returns:
            {"created": int, "updated": int, "total_api": int}
        """
        # 1. 获取账户信息
        account = await PixelAccount.filter(id=account_id).first()
        if not account:
            raise ValueError(f"像素账户不存在: id={account_id}")

        # 2. 获取 token
        token = await get_pixel_token(
            username=account.username,
            password=account.password,
            org=account.tenant_address,
        )
        if not token:
            raise ValueError("像素平台 token 获取失败，请检查账户配置")

        # 3. 分页调用病害数据 API，处理可能超过 5000 条的情况
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        }

        page = 1
        limit = 5000
        total_api = 0
        created = 0
        updated = 0

        async with httpx.AsyncClient(timeout=120) as client:
            while True:
                payload = json.dumps({
                    "id": "",
                    "regionId": [],
                    "companyId": [],
                    "roadName": [],
                    "roadStakes": [],
                    "riskName": [],
                    "roadNameLike": "",
                    "riskLevel": [],
                    "riskStatus": [],
                    "searchType": 0,
                    "carType": [],
                    "carIds": [],
                    "startTime": start_time,
                    "endTime": end_time,
                    "isMesSend": "",
                    "isUpload": "",
                    "page": page,
                    "limit": limit,
                })

                response = await client.post(DEFECT_API_URL, content=payload, headers=headers)
                if response.status_code != 200:
                    raise ValueError(f"病害数据 API 请求失败: status={response.status_code}")

                data = response.json()
                if data.get("statusCode") != 200:
                    raise ValueError(f"病害数据 API 返回错误: {data.get('message', 'unknown')}")

                records = data.get("data", {}).get("list", [])
                if page == 1:
                    total_api = data.get("data", {}).get("total", 0)

                if not records:
                    break

                for record in records:
                    remote_id = record.get("id", "")
                    # 检查是否已存在
                    existing = await Defect.filter(
                        remote_id=remote_id,
                        pixel_account_id=account_id,
                    ).first()

                    defect_data = {
                        "remote_id": remote_id,
                        "pixel_account_id": account_id,
                        "longitude": record.get("longitude"),
                        "latitude": record.get("latitude"),
                        "longitude_gc": record.get("longitudeGc"),
                        "latitude_gc": record.get("latitudeGc"),
                        "track_image": record.get("trackImage"),
                        "track_url": record.get("trackUrl"),
                        "status": record.get("status"),
                        "status_name": record.get("statusName"),
                        "risk_type": record.get("riskType"),
                        "risk_level": record.get("riskLevel"),
                        "risk_level_name": record.get("riskLevelName"),
                        "risk_name1": record.get("riskName1"),
                        "risk_name2": record.get("riskName2"),
                        "risk_name3": record.get("riskName3"),
                        "risk_time": record.get("riskTime"),
                        "city_code": record.get("cityCode"),
                        "city_name": record.get("cityName"),
                        "org_code": record.get("orgCode"),
                        "road_name": record.get("roadName"),
                        "data_from": record.get("dataFrom"),
                        "data_from_name": record.get("dataFromName"),
                        "region_name": record.get("regionName"),
                        "town_name": record.get("townName"),
                        "subd_name": record.get("subdName"),
                        "reverse_name": record.get("reverseName"),
                        "car_no": record.get("carNo"),
                        "lane": record.get("lane"),
                        "extra_data": record,
                    }

                    if existing:
                        await existing.update_from_dict(defect_data).save()
                        updated += 1
                    else:
                        await Defect.create(**defect_data)
                        created += 1

                if total_api and page * limit >= total_api:
                    break

                page += 1

        logger.info(
            f"病害数据同步完成: account_id={account_id}, "
            f"api_total={total_api}, created={created}, updated={updated}"
        )

        return {"created": created, "updated": updated, "total_api": total_api}

    async def sync_stream(self, user_id: int, account_id: int, start_time: str, end_time: str):
        """
        流式同步病害数据：通过 SSE 推送分页进度。

        异步生成器，每次 yield 一条 SSE 格式的字符串。
        事件类型:
          - start:   同步开始，含 total_pages / total_api
          - progress: 每页完成后的进度
          - done:    全部完成，含 created / updated
          - error:   出错，含 message
        """
        import json as _json

        def _sse(event: str, data: dict) -> str:
            return f"event: {event}\ndata: {_json.dumps(data, ensure_ascii=False)}\n\n"

        # 1. 获取账户信息
        account = await PixelAccount.filter(id=account_id).first()
        if not account:
            yield _sse("error", {"message": f"像素账户不存在: id={account_id}"})
            return

        # 2. 获取 token
        token = await get_pixel_token(
            username=account.username,
            password=account.password,
            org=account.tenant_address,
        )
        if not token:
            yield _sse("error", {"message": "像素平台 token 获取失败，请检查账户配置"})
            return

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        }

        limit = 5000
        total_api = 0
        total_pages = 0
        created = 0
        updated = 0
        current_page = 0

        try:
            async with httpx.AsyncClient(timeout=120) as client:
                page = 1
                while True:
                    payload = _json.dumps({
                        "id": "",
                        "regionId": [],
                        "companyId": [],
                        "roadName": [],
                        "roadStakes": [],
                        "riskName": [],
                        "roadNameLike": "",
                        "riskLevel": [],
                        "riskStatus": [],
                        "searchType": 0,
                        "carType": [],
                        "carIds": [],
                        "startTime": start_time,
                        "endTime": end_time,
                        "isMesSend": "",
                        "isUpload": "",
                        "page": page,
                        "limit": limit,
                    })

                    response = await client.post(DEFECT_API_URL, content=payload, headers=headers)
                    if response.status_code != 200:
                        yield _sse("error", {"message": f"病害数据 API 请求失败: status={response.status_code}"})
                        return

                    data = response.json()
                    if data.get("statusCode") != 200:
                        yield _sse("error", {"message": f"病害数据 API 返回错误: {data.get('message', 'unknown')}"})
                        return

                    records = data.get("data", {}).get("list", [])

                    # 首页：计算总页数，发送 start 事件
                    if page == 1:
                        total_api = data.get("data", {}).get("total", 0)
                        total_pages = (total_api + limit - 1) // limit if total_api else 0
                        yield _sse("start", {
                            "total_pages": total_pages,
                            "total_api": total_api,
                            "page_size": limit,
                        })

                    if not records:
                        break

                    # 处理当前页的记录
                    for record in records:
                        remote_id = record.get("id", "")
                        existing = await Defect.filter(
                            remote_id=remote_id,
                            pixel_account_id=account_id,
                        ).first()

                        defect_data = {
                            "remote_id": remote_id,
                            "pixel_account_id": account_id,
                            "longitude": record.get("longitude"),
                            "latitude": record.get("latitude"),
                            "longitude_gc": record.get("longitudeGc"),
                            "latitude_gc": record.get("latitudeGc"),
                            "track_image": record.get("trackImage"),
                            "track_url": record.get("trackUrl"),
                            "status": record.get("status"),
                            "status_name": record.get("statusName"),
                            "risk_type": record.get("riskType"),
                            "risk_level": record.get("riskLevel"),
                            "risk_level_name": record.get("riskLevelName"),
                            "risk_name1": record.get("riskName1"),
                            "risk_name2": record.get("riskName2"),
                            "risk_name3": record.get("riskName3"),
                            "risk_time": record.get("riskTime"),
                            "city_code": record.get("cityCode"),
                            "city_name": record.get("cityName"),
                            "org_code": record.get("orgCode"),
                            "road_name": record.get("roadName"),
                            "data_from": record.get("dataFrom"),
                            "data_from_name": record.get("dataFromName"),
                            "region_name": record.get("regionName"),
                            "town_name": record.get("townName"),
                            "subd_name": record.get("subdName"),
                            "reverse_name": record.get("reverseName"),
                            "car_no": record.get("carNo"),
                            "lane": record.get("lane"),
                            "extra_data": record,
                        }

                        if existing:
                            await existing.update_from_dict(defect_data).save()
                            updated += 1
                        else:
                            await Defect.create(**defect_data)
                            created += 1

                    # 每页完成后发送进度事件
                    current_page = page
                    yield _sse("progress", {
                        "page": current_page,
                        "total_pages": total_pages,
                        "total_api": total_api,
                        "created": created,
                        "updated": updated,
                        "message": f"正在同步第 {current_page}/{total_pages} 页",
                    })

                    if total_api and page * limit >= total_api:
                        break
                    page += 1

            # 全部完成
            logger.info(
                f"病害数据流式同步完成: account_id={account_id}, "
                f"api_total={total_api}, created={created}, updated={updated}"
            )
            yield _sse("done", {
                "created": created,
                "updated": updated,
                "total_api": total_api,
                "total_pages": total_pages,
                "message": f"同步完成：新增 {created} 条，更新 {updated} 条，API 共 {total_api} 条",
            })

        except Exception as e:
            logger.error(f"病害数据流式同步异常: {e}")
            yield _sse("error", {"message": str(e)})

    async def clear(self, user_id: int, account_id: int) -> int:
        """
        清除指定账户的所有病害数据。

        Returns:
            删除的记录数
        """
        count = await Defect.filter(pixel_account_id=account_id).count()
        await Defect.filter(pixel_account_id=account_id).delete()
        logger.info(f"病害数据清除完成: account_id={account_id}, deleted={count}")
        return count

    async def list_defects(
        self,
        user_id: int,
        page: int = 1,
        page_size: int = 10,
        account_id: Optional[int] = None,
        road_name: Optional[str] = None,
        risk_level_name: Optional[str] = None,
        status_name: Optional[str] = None,
    ):
        """分页查询病害数据，仅显示当前用户有权限的像素账户数据"""
        q = Q()

        # 只显示用户关联的账户数据
        user_accounts = await PixelAccount.filter(users__id=user_id).values_list("id", flat=True)
        if not user_accounts:
            return 0, []
        q &= Q(pixel_account_id__in=list(user_accounts))

        if account_id:
            q &= Q(pixel_account_id=account_id)
        if road_name:
            q &= Q(road_name__contains=road_name)
        if risk_level_name:
            q &= Q(risk_level_name__contains=risk_level_name)
        if status_name:
            q &= Q(status_name__contains=status_name)

        total = await Defect.filter(q).count()
        objs = await Defect.filter(q).offset((page - 1) * page_size).limit(page_size).order_by("-risk_time")

        data = []
        for obj in objs:
            d = {
                "id": obj.id,
                "remote_id": obj.remote_id,
                "pixel_account_id": obj.pixel_account_id,
                "longitude": obj.longitude,
                "latitude": obj.latitude,
                "track_image": obj.track_image,
                "status_name": obj.status_name,
                "risk_level": obj.risk_level,
                "risk_level_name": obj.risk_level_name,
                "risk_name3": obj.risk_name3,
                "risk_time": obj.risk_time.isoformat() if obj.risk_time else None,
                "city_name": obj.city_name,
                "road_name": obj.road_name,
                "data_from_name": obj.data_from_name,
                "car_no": obj.car_no,
                "created_at": obj.created_at.isoformat() if obj.created_at else None,
            }
            data.append(d)

        return total, data


defect_controller = DefectController()
