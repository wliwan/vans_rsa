"""车辆状态检测 Controller — 复用 TrackController 车辆查询 + 享速设备 API 调用"""
from app.controllers.track import track_controller
from app.log import logger
from app.utils.xiangsu_api import get_device_flow, get_device_info, get_device_status


class VehicleController:
    """车辆状态检测控制器

    复用 TrackController 的账户/车型/车辆列表查询，
    封装享速设备 API 的在线状态和设备信息获取。
    """

    # ── 复用 TrackController 的车辆选择能力 ──

    async def get_user_accounts(self, user_id: int):
        """获取用户关联的像素账户列表"""
        return await track_controller.get_user_accounts(user_id)

    async def get_car_types(self, account_id: int):
        """获取指定账户的可用车型列表"""
        return await track_controller.get_car_types(account_id)

    async def get_cars(self, account_id: int, car_type: int):
        """获取指定账户和车型下的车辆列表"""
        return await track_controller.get_cars(account_id, car_type)

    # ── 享速设备 API ──

    async def check_status(self, car_id: str) -> dict:
        """检测设备在线状态"""
        logger.info(f"车辆状态检测请求: car_id={car_id}")
        return await get_device_status(car_id)

    async def get_info(self, car_id: str) -> dict:
        """获取设备完整信息（含 jsonReport 统计）"""
        logger.info(f"车辆设备信息请求: car_id={car_id}")
        return await get_device_info(car_id)

    async def full_check(self, car_id: str) -> dict:
        """一站式检测：在线状态 + 设备信息"""
        logger.info(f"车辆全面检测请求: car_id={car_id}")
        status_result = await get_device_status(car_id)
        info_result = await get_device_info(car_id)

        return {
            "status": status_result,
            "device": info_result,
        }

    async def refresh_status(self, car_id: str) -> dict:
        """刷新设备在线状态（仅状态，不含设备信息）"""
        logger.info(f"刷新设备状态请求: car_id={car_id}")
        return await get_device_status(car_id)

    async def query_flow(self, car_id: str, date: str) -> dict:
        """查询设备数据流量 + 刷新设备信息"""
        logger.info(f"设备流量查询请求: car_id={car_id}, date={date}")
        flow_result = await get_device_flow(car_id, date)
        # 查询流量后自动刷新设备信息
        info_result = await get_device_info(car_id)
        return {
            "flow": flow_result,
            "device": info_result,
        }


vehicle_controller = VehicleController()
