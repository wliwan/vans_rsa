from fastapi import APIRouter

from app.core.dependency import DependPermission

from .ai_proxy import ai_proxy_router
from .apis import apis_router
from .auditlog import auditlog_router
from .base import base_router
from .defects import defects_router
from .depts import depts_router
from .tracks import tracks_router
from .menus import menus_router
from .pixel_accounts import pixel_accounts_router
from .regions import regions_router
from .roles import roles_router
from .skills import skills_router
from .users import users_router
from .vehicle import vehicle_router
from .report import report_router
from .workspace import workspace_router

v1_router = APIRouter()

v1_router.include_router(base_router, prefix="/base")
v1_router.include_router(users_router, prefix="/user", dependencies=[DependPermission])
v1_router.include_router(roles_router, prefix="/role", dependencies=[DependPermission])
v1_router.include_router(menus_router, prefix="/menu", dependencies=[DependPermission])
v1_router.include_router(ai_proxy_router, prefix="/ai-proxy", dependencies=[DependPermission])
v1_router.include_router(apis_router, prefix="/api", dependencies=[DependPermission])
v1_router.include_router(depts_router, prefix="/dept", dependencies=[DependPermission])
v1_router.include_router(auditlog_router, prefix="/auditlog", dependencies=[DependPermission])
v1_router.include_router(pixel_accounts_router, prefix="/pixel-account", dependencies=[DependPermission])
v1_router.include_router(defects_router, prefix="/defect", dependencies=[DependPermission])
v1_router.include_router(tracks_router, prefix="/track", dependencies=[DependPermission])
v1_router.include_router(regions_router, prefix="/region", dependencies=[DependPermission])
v1_router.include_router(skills_router, prefix="/skill", dependencies=[DependPermission])
v1_router.include_router(workspace_router, prefix="/workspace", dependencies=[DependPermission])
v1_router.include_router(vehicle_router, prefix="/vehicle", dependencies=[DependPermission])
v1_router.include_router(report_router, prefix="/report", dependencies=[DependPermission])



