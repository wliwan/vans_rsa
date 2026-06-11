"""
享速设备 API 工具模块
提供车辆设备在线状态检测、设备信息查询等功能

API 端点:
- 设备状态:   POST http://c.xiangsu.work:9999/g2/proxy/api/set-json-parameter?carid={carid}
- 设备信息:   GET  http://c.xiangsu.work:9999/g2/proxy/api/terminal2?carid={carid}
"""
import json
from typing import Optional

import httpx
import re
from app.log import logger

# 享速设备 API 基础地址
XIANGSU_DEVICE_BASE = "http://c.xiangsu.work:9999/g2/proxy/api"
XIANGSU_STATUS_URL = f"{XIANGSU_DEVICE_BASE}/set-json-parameter"
XIANGSU_INFO_URL = f"{XIANGSU_DEVICE_BASE}/terminal2"
XIANGSU_FLOW_URL = f"{XIANGSU_DEVICE_BASE}/flow"


async def get_device_status(car_id: str) -> dict:
    """
    检测车辆设备在线状态。

    POST 到享速设备 API，请求 GET_DEVICE_STATISTICS。

    Args:
        car_id: 车辆ID（carid 参数）

    Returns:
        {
            "online": bool,          # 是否在线
            "status": int,           # 原始 status 码 (0=在线, -1=离线等)
            "data": str,             # 原始 data 字段
            "raw": dict,             # 完整原始响应
        }
    """
    url = f"{XIANGSU_STATUS_URL}?carid={car_id}"
    payload = json.dumps({"GET_DEVICE_STATISTICS": {}})
    headers = {"Content-Type": "application/json"}

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.post(url, content=payload, headers=headers)

        data = response.json()
        status = data.get("status", -1)
        online = status == 0

        logger.info(f"车辆设备状态检测: car_id={car_id}, online={online}, status={status}")

        return {
            "online": online,
            "status": status,
            "data": data.get("data", ""),
            "raw": data,
        }
    except httpx.TimeoutException:
        logger.error(f"车辆设备状态检测超时: car_id={car_id}")
        raise ValueError(f"设备状态检测超时: car_id={car_id}")
    except Exception as e:
        logger.error(f"车辆设备状态检测异常: {e}, car_id={car_id}")
        raise ValueError(f"设备状态检测失败: {e}")


async def get_device_info(car_id: str) -> dict:
    """
    获取车辆设备完整信息（含 jsonReport 统计）。

    GET 到享速设备 API /terminal2。

    Args:
        car_id: 车辆ID（carid 参数）

    Returns:
        {
            "car_id": str,                 # 车牌号
            "online": bool,                # 是否在线 (来自 info.off)
            "info": {                      # 位置与状态信息
                "longitude": float,
                "latitude": float,
                "speed": float,            # 速度 (km/h)
                "angle": float,            # 方位角
                "car_state": int,          # 车辆状态码
                "last_report_time": int,   # 最后上报时间戳
            },
            "wrapper": {                   # 设备包装信息
                "ip_addr": str,
                "city": str,
                "device_id": str,
                "imei": str,
                "iccid": str,
                "hardware": str,           # 硬件信息
                "software": str,           # 软件版本
                "protocol_version": int,
                "last_image_list": list,   # 最近图像列表
            },
            "statistics": dict,            # 解析后的 DEVICE_STATISTICS
            "raw": dict,                   # 完整原始响应
        }
    """
    url = f"{XIANGSU_INFO_URL}?carid={car_id}"

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.get(url)

        data = response.json()
        wrapper = data.get("wrapper", {})
        info = data.get("info", {})

        # 解析 jsonReport 中的 DEVICE_STATISTICS
        statistics = {}
        json_report_str = wrapper.get("jsonReport", "")
        if json_report_str:
            try:
                report = json.loads(json_report_str)
                statistics = report.get("DEVICE_STATISTICS", {})
            except (json.JSONDecodeError, TypeError):
                logger.warning(f"jsonReport 解析失败: car_id={car_id}")
        flow_report={}
        flowData_str = wrapper.get("flowData", "")
        print(flowData_str)
        if flowData_str and isinstance(flowData_str, str):
            try:
                flow_report = json.loads(flowData_str)
            except (json.JSONDecodeError, TypeError):
                m = re.search(r'flowData\{([^}]+(?:\{[^}]*\}[^}]*)*)\}', flowData_str)
                if m:
                    inner = m.group(1)
                    fd = {}
                    # 提取简单键值对
                    for kv in re.findall(r'(\w+)=([^,\]]+)', inner):
                        key, val = kv[0], kv[1].strip()
                        try:
                            fd[key] = int(val)
                        except ValueError:
                            fd[key] = val
                    # 提取 detail 数组
                    detail_m = re.search(r'detail=\[([^\]]+)\]', inner)
                    if detail_m:
                        detail_items = []
                        for item in detail_m.group(1).split('],') if '],' in detail_m.group(1) else [detail_m.group(1)]:
                            item = item.strip().rstrip(']').lstrip('[')
                            d = {}
                            for dkv in re.findall(r'(\w+):([^,\]]+)', item):
                                dk, dv = dkv[0], dkv[1].strip()
                                try:
                                    d[dk] = int(dv)
                                except ValueError:
                                    d[dk] = dv
                            detail_items.append(d)
                        fd["detail"] = detail_items
                    flow_report = fd
                else:
                    logger.warning(f"流量响应非 JSON 且解析失败: car_id={car_id}")

        # online 状态: off=false 表示在线
        online = not info.get("off", True)

        logger.info(f"车辆设备信息获取成功: car_id={car_id}, online={online}")

        return {
            "car_id": info.get("carNo", car_id),
            "online": online,
            "info": {
                "longitude": info.get("lon"),
                "latitude": info.get("lat"),
                "speed": info.get("speed"),
                "angle": info.get("angle"),
                "car_state": info.get("carState"),
                "last_report_time": info.get("lastReponseTime"),
            },
            "wrapper": {
                "ip_addr": wrapper.get("ipAddr"),
                "city": wrapper.get("city"),
                "device_id": wrapper.get("deviceId"),
                "imei": wrapper.get("imei"),
                "iccid": wrapper.get("iccid"),
                "hardware": wrapper.get("hardware"),
                "software": wrapper.get("software"),
                "protocol_version": wrapper.get("protocolVersion"),
                "last_image_list": wrapper.get("lastImageListWithChannel", []),
                "flow_report": flow_report,
            },
            "statistics": statistics,
            "raw": data,
        }
    except httpx.TimeoutException:
        logger.error(f"车辆设备信息获取超时: car_id={car_id}")
        raise ValueError(f"设备信息获取超时: car_id={car_id}")
    except Exception as e:
        logger.error(f"车辆设备信息获取异常: {e}, car_id={car_id}")
        raise ValueError(f"设备信息获取失败: {e}")


async def get_device_flow(car_id: str, date: str) -> dict:
    """
    查询车辆设备某日的数据流量使用情况。

    GET 到享速设备 API /flow?carid={carid}&date={YYYY-MM-DD}。
    解析响应中的 wrapper.flowData 字段。

    Args:
        car_id: 车辆ID（carid 参数）
        date: 查询日期，格式 YYYY-MM-DD

    Returns:
        {
            "ok": bool,              # 是否查询成功 (status_code==200)
            "status_code": int,      # HTTP 状态码
            "date": str,             # 查询日期
            "flow": {                # 流量数据（可能为 null）
                "year": int,
                "month": int,
                "day": int,
                "send": int,         # 上传字节数
                "receive": int,      # 下载字节数
                "detail": [...]      # IP 级别的明细
            },
        }
    """

    url = f"{XIANGSU_FLOW_URL}?carid={car_id}&date={date}"

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.get(url)

        ok = response.status_code == 200
        text = response.text.strip() or ""

        # 解析 wrapper.flowData
        flow_data = None
        if text:
            try:
                device_info = await get_device_info(car_id)

                flow_data = device_info.get("wrapper", {}).get("flow_report")
                print(flow_data)
            except Exception as e:
                logger.warning(f"流量数据解析异常: {e}, car_id={car_id}")

        logger.info(f"车辆流量查询: car_id={car_id}, date={date}, ok={ok}, has_flow={flow_data is not None}")

        return {
            "ok": ok,
            "status_code": response.status_code,
            "date": date,
            "flow": flow_data,
        }
    except httpx.TimeoutException:
        logger.error(f"车辆流量查询超时: car_id={car_id}, date={date}")
        raise ValueError(f"流量查询超时: car_id={car_id}")
    except Exception as e:
        logger.error(f"车辆流量查询异常: {e}, car_id={car_id}, date={date}")
        raise ValueError(f"流量查询失败: {e}")
