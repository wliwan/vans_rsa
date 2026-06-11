from typing import List

from app.core.crud import CRUDBase
from app.models.admin import PixelAccount, User
from app.schemas.pixel_accounts import PixelAccountCreate, PixelAccountUpdate
from app.utils.pixel_api import get_account_location, get_base_info


class PixelAccountController(CRUDBase[PixelAccount, PixelAccountCreate, PixelAccountUpdate]):
    def __init__(self):
        super().__init__(model=PixelAccount)

    async def update_users(self, account: PixelAccount, user_ids: List[int]) -> None:
        """更新可访问的VFA用户关联"""
        await account.users.clear()
        for user_id in user_ids:
            user_obj = await User.filter(id=user_id).first()
            if user_obj:
                await account.users.add(user_obj)

    async def create_account(self, obj_in: PixelAccountCreate) -> PixelAccount:
        """创建像素账户（含 token 校验和位置信息获取）"""
        # 获取 base_url 和 renter
        base_info = get_base_info(obj_in.tenant_address)

        # 通过像素平台 API 校验账户并获取位置信息
        location_info = await get_account_location(
            username=obj_in.username,
            password=obj_in.password,
            org=obj_in.tenant_address,
        )

        # 校验失败则抛出异常
        if location_info["token"] is None:
            from fastapi.exceptions import HTTPException
            raise HTTPException(
                status_code=400,
                detail="像素平台账户校验失败：无法获取 access token，请检查用户名、密码和租户地址是否正确",
            )

        # 构建创建数据
        obj_dict = obj_in.model_dump(exclude={"user_ids"})
        obj_dict["base_url"] = base_info["base_url"]
        obj_dict["renter"] = base_info["renter"]
        obj_dict["country"] = location_info["country"]
        obj_dict["state"] = location_info["state"]

        # 创建账户
        obj = self.model(**obj_dict)
        await obj.save()

        # 关联用户
        if obj_in.user_ids:
            await self.update_users(obj, obj_in.user_ids)

        return obj

    async def update_account(self, obj_in: PixelAccountUpdate) -> PixelAccount:
        """更新像素账户（含重新 token 校验和位置信息获取）"""
        # 获取 base_url 和 renter
        base_info = get_base_info(obj_in.tenant_address)

        # 通过像素平台 API 重新校验账户
        location_info = await get_account_location(
            username=obj_in.username,
            password=obj_in.password,
            org=obj_in.tenant_address,
        )

        if location_info["token"] is None:
            from fastapi.exceptions import HTTPException
            raise HTTPException(
                status_code=400,
                detail="像素平台账户校验失败：无法获取 access token，请检查用户名、密码和租户地址是否正确",
            )

        # 更新账户
        obj = await self.get(id=obj_in.id)
        update_dict = obj_in.model_dump(exclude_unset=True, exclude={"id", "user_ids"})
        update_dict["base_url"] = base_info["base_url"]
        update_dict["renter"] = base_info["renter"]
        update_dict["country"] = location_info["country"]
        update_dict["state"] = location_info["state"]

        obj = obj.update_from_dict(update_dict)
        await obj.save()

        # 更新用户关联
        if obj_in.user_ids is not None:
            await self.update_users(obj, obj_in.user_ids)

        return obj


pixel_account_controller = PixelAccountController()
