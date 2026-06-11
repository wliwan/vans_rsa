"""
像素平台 API 工具模块
提供 token 获取、用户信息查询、逆向地理编码等功能
"""
import json
from typing import Optional

import httpx

from app.log import logger

# 像素平台固定配置
PIXEL_BASE_URL = "https://road.xiangsu.work"
PIXEL_TOKEN_URL = f"{PIXEL_BASE_URL}/bvr-gate/api/badmin/b/jwt/token"
PIXEL_USER_AUTH_URL = f"{PIXEL_BASE_URL}/bvr-gate/api/badmin/b/user/userAuth"



# OSM Nominatim API
NOMINATIM_URL = "https://nominatim.openstreetmap.org/reverse"


def get_base_info(tenant_address: str) -> dict:
    """
    通过租户地址获取 base_url 和 renter。

    Args:
        tenant_address: 租户地址（org 标识）

    Returns:
        {"base_url": str, "renter": str}
    """
    return {
        "base_url": PIXEL_BASE_URL,
        "renter": tenant_address,
    }


async def get_pixel_token(username: str, password: str, org: str) -> Optional[str]:
    """
    调用像素平台 API 获取 access token。

    Args:
        username: 像素平台用户名
        password: 像素平台密码
        org: 租户标识

    Returns:
        access_token 字符串，获取失败返回 None
    """
    try:
        payload = json.dumps({
            "userName": username,
            "pwd": password,
            "index": org,
        })
        headers = {
            "Referer": f"{PIXEL_BASE_URL}/bvr/{org}/",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(PIXEL_TOKEN_URL, content=payload, headers=headers)

        if response.status_code == 200:
            data = response.json()
            if "data" in data and "accessToken" in data["data"]:
                logger.info(f"像素平台 token 获取成功: user={username}, org={org}")
                return data["data"]["accessToken"]
            else:
                logger.warning(f"像素平台 token 响应中未找到 accessToken: user={username}, org={org}")
                return None
        else:
            logger.warning(f"像素平台 token 请求失败: status={response.status_code}, user={username}, org={org}")
            return None
    except Exception as e:
        logger.error(f"像素平台 token 获取异常: {e}, user={username}, org={org}")
        return None


async def get_user_auth_info(token: str) -> Optional[str]:
    """
    通过 token 获取用户授权信息，返回 centerPoint（经纬度坐标字符串 "lon,lat"）。

    Args:
        token: 像素平台 access token

    Returns:
        centerPoint 字符串（如 "120.123,30.456"），获取失败返回 None
    """
    try:
        headers = {
            "Authorization": f"Bearer {token}",
        }

        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(PIXEL_USER_AUTH_URL, headers=headers)

        if response.status_code == 200:
            data = response.json()
            position = data.get("centerPoint")
            if position:
                logger.info(f"像素平台用户授权信息获取成功: centerPoint={position}")
                return position
            else:
                logger.warning("像素平台用户授权信息中未找到 centerPoint")
                return None
        else:
            logger.warning(f"像素平台用户授权信息请求失败: status={response.status_code}")
            return None
    except Exception as e:
        logger.error(f"像素平台用户授权信息获取异常: {e}")
        return None


async def reverse_geocode_osm(lon: str, lat: str) -> Optional[dict]:
    """
    使用 OSM Nominatim API 进行逆向地理编码。

    Args:
        lon: 经度
        lat: 纬度

    Returns:
        {"country": str, "state": str} 或 None
    """
    try:
        params = {
            "format": "json",
            "lat": lat,
            "lon": lon,
            "zoom": 10,
            "accept-language": "zh",
        }
        headers = {
            "User-Agent": "VueFastAPIAdmin/1.0",
        }

        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.get(NOMINATIM_URL, params=params, headers=headers)

        if response.status_code == 200:
            data = response.json()
            address = data.get("address", {})
            country = address.get("country", "")
            state = address.get("state", address.get("region", ""))
            logger.info(f"OSM 逆向地理编码成功: lon={lon}, lat={lat}, country={country}, state={state}")
            return {"country": country, "state": state}
        else:
            logger.warning(f"OSM 逆向地理编码失败: status={response.status_code}")
            return None
    except Exception as e:
        logger.error(f"OSM 逆向地理编码异常: {e}")
        return None


async def reverse_geocode_mapbox(lon: str, lat: str) -> Optional[dict]:
    """
    使用 Mapbox Geocoding API 进行逆向地理编码（备用方案）。

    Args:
        lon: 经度
        lat: 纬度

    Returns:
        {"country": str, "state": str} 或 None
    """
    try:
        url = f"https://api.mapbox.com/geocoding/v5/mapbox.places/{lon},{lat}.json"
        params = {
            "access_token": "",
            "language": "zh",
            "types": "country,region",
        }

        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.get(url, params=params)

        if response.status_code == 200:
            data = response.json()
            features = data.get("features", [])
            country = ""
            state = ""
            for feature in features:
                place_type = feature.get("place_type", [])
                text = feature.get("text", "")
                if "country" in place_type:
                    country = text
                elif "region" in place_type:
                    state = text
            logger.info(f"Mapbox 逆向地理编码成功: lon={lon}, lat={lat}, country={country}, state={state}")
            return {"country": country, "state": state}
        else:
            logger.warning(f"Mapbox 逆向地理编码失败: status={response.status_code}")
            return None
    except Exception as e:
        logger.error(f"Mapbox 逆向地理编码异常: {e}")
        return None


async def get_account_location(username: str, password: str, org: str) -> dict:
    """
    获取像素账户的国家/区域信息。

    流程：
    1. 通过用户名、密码、org 获取 token（校验）
    2. 通过 token 获取用户授权信息（含 centerPoint 坐标）
    3. 通过坐标逆向地理编码获取国家/区域
    4. 优先使用 OSM，失败则使用 Mapbox

    Args:
        username: 像素平台用户名
        password: 像素平台密码
        org: 租户标识

    Returns:
        {"country": str, "state": str, "token": str} — token 为 None 表示校验失败
    """
    # Step 1: 获取 token
    token = await get_pixel_token(username, password, org)
    if not token:
        return {"country": "", "state": "", "token": None}

    # Step 2: 获取坐标
    position = await get_user_auth_info(token)
    if not position:
        return {"country": "", "state": "", "token": token}

    # Step 3: 解析经纬度
    try:
        lon, lat = position.split(",")
        lon, lat = lon.strip(), lat.strip()
    except (ValueError, AttributeError):
        logger.warning(f"坐标解析失败: position={position}")
        return {"country": "", "state": "", "token": token}

    # Step 4: 逆向地理编码（OSM 优先，失败则 Mapbox）
    location = await reverse_geocode_osm(lon, lat)
    if location:
        return {"country": location["country"], "state": location["state"], "token": token}

    location = await reverse_geocode_mapbox(lon, lat)
    if location:
        return {"country": location["country"], "state": location["state"], "token": token}

    return {"country": "", "state": "", "token": token}
