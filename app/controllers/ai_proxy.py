from typing import List

from app.core.crud import CRUDBase
from app.models.admin import AIProxy, User
from app.schemas.ai_proxy import AIProxyCreate, AIProxyUpdate


class AIProxyController(CRUDBase[AIProxy, AIProxyCreate, AIProxyUpdate]):
    def __init__(self):
        super().__init__(model=AIProxy)

    async def get_accessible(self, user_id: int, page: int, page_size: int):
        """获取用户可访问的 AI 代理列表"""
        total = await self.model.filter(users__id=user_id).count()
        objs = await (
            self.model.filter(users__id=user_id)
            .offset((page - 1) * page_size)
            .limit(page_size)
            .order_by("-updated_at")
            .prefetch_related("users")
        )
        return total, objs

    async def check_permission(self, proxy_id: int, user_id: int):
        """检查用户是否有权限"""
        return await self.model.filter(id=proxy_id, users__id=user_id).first()

    async def update_users(self, proxy: AIProxy, user_ids: List[int]):
        await proxy.users.clear()
        for uid in user_ids:
            user = await User.filter(id=uid).first()
            if user:
                await proxy.users.add(user)


ai_proxy_controller = AIProxyController()
