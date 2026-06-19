from typing import List, Optional
import logging

from app.core.crud import CRUDBase
from app.models.admin import AIProxy, User
from app.schemas.ai_proxy import AIProxyCreate, AIProxyUpdate

logger = logging.getLogger(__name__)


class AIProxyController(CRUDBase[AIProxy, AIProxyCreate, AIProxyUpdate]):
    def __init__(self):
        super().__init__(model=AIProxy)

    async def get_by_name(self, name: str) -> Optional[AIProxy]:
        """按名称（关键字段）查找代理"""
        return await self.model.filter(name=name).first()

    async def create_or_update(self, obj_in: AIProxyCreate) -> AIProxy:
        """基于名称的 upsert：存在则更新，不存在则创建"""
        obj_dict = obj_in.create_dict()
        existing = await self.get_by_name(obj_in.name)
        if existing:
            # 存在：更新非 name 字段
            await self.update(id=existing.id, obj_in=obj_dict)
            return existing
        else:
            # 不存在：创建
            return await self.create(obj_in=obj_dict)

    async def get_accessible(self, user_id: int, page: int, page_size: int):
        """获取用户可访问的 AI 代理列表（超级管理员返回全部）"""
        if await self._is_superuser(user_id):
            qs = self.model.all()
            total = await qs.count()
        else:
            qs = self.model.filter(users__id=user_id)
            total = await qs.count()
        objs = await (
            qs.offset((page - 1) * page_size)
            .limit(page_size)
            .order_by("-updated_at")
            .prefetch_related("users")
        )
        return total, objs

    async def _is_superuser(self, user_id: int) -> bool:
        """检查用户是否为超级管理员"""
        user = await User.filter(id=user_id).first()
        return user is not None and user.is_superuser

    async def check_permission(self, proxy_id: int, user_id: int):
        """按 ID 检查用户是否有权限（超级管理员始终有权限）"""
        if await self._is_superuser(user_id):
            return await self.model.filter(id=proxy_id).first()
        return await self.model.filter(id=proxy_id, users__id=user_id).first()

    async def check_permission_by_name(self, name: str, user_id: int):
        """按名称检查用户是否有权限（超级管理员始终有权限）"""
        if await self._is_superuser(user_id):
            return await self.get_by_name(name)
        return await self.model.filter(name=name, users__id=user_id).first()

    async def update_by_name(self, name: str, obj_in: dict) -> Optional[AIProxy]:
        """基于名称更新：找到 name 对应的记录，用 obj_in 更新其他字段"""
        proxy = await self.get_by_name(name)
        if not proxy:
            return None
        update_data = {k: v for k, v in obj_in.items() if k != "name"}
        if update_data:
            await self.update(id=proxy.id, obj_in=update_data)
        return proxy

    async def remove_by_name(self, name: str) -> bool:
        """基于名称删除"""
        proxy = await self.get_by_name(name)
        if not proxy:
            return False
        await self.remove(id=proxy.id)
        return True

    async def update_users(self, proxy: AIProxy, user_ids: List[int]):
        """更新授权用户列表（清空 + 重建）"""
        await proxy.users.clear()
        for uid in user_ids:
            user = await User.filter(id=uid).first()
            if user:
                await proxy.users.add(user)


ai_proxy_controller = AIProxyController()
