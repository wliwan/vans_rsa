from typing import List, Optional

from app.core.crud import CRUDBase
from app.models.admin import Skill
from app.schemas.skills import SkillCreate, SkillUpdate


class SkillController(CRUDBase[Skill, SkillCreate, SkillUpdate]):
    def __init__(self):
        super().__init__(model=Skill)

    async def get_accessible_skills(self, user_id: int, page: int, page_size: int):
        """获取用户可访问的 Skill（该用户在 users 关联中）"""
        total = await self.model.filter(users__id=user_id).count()
        objs = await (
            self.model.filter(users__id=user_id)
            .offset((page - 1) * page_size)
            .limit(page_size)
            .order_by("-updated_at")
            .prefetch_related("users")
        )
        return total, objs

    async def check_permission(self, skill_id: int, user_id: int) -> Optional[Skill]:
        """检查用户是否有权限访问该 Skill"""
        skill = await self.model.filter(id=skill_id, users__id=user_id).first()
        return skill

    async def update_users(self, skill: Skill, user_ids: List[int]) -> None:
        """更新 Skill 的可访问用户"""
        await skill.users.clear()
        from app.models.admin import User
        for user_id in user_ids:
            user_obj = await User.filter(id=user_id).first()
            if user_obj:
                await skill.users.add(user_obj)


skill_controller = SkillController()
