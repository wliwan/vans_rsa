import shutil

from aerich import Command
from fastapi import FastAPI
from fastapi.middleware import Middleware
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from tortoise.expressions import Q

from app.api import api_router
from app.controllers.api import api_controller
from app.controllers.user import UserCreate, user_controller
from app.core.exceptions import (
    DoesNotExist,
    DoesNotExistHandle,
    HTTPException,
    HttpExcHandle,
    IntegrityError,
    IntegrityHandle,
    RequestValidationError,
    RequestValidationHandle,
    ResponseValidationError,
    ResponseValidationHandle,
)
from app.log import logger
from app.models.admin import Api, Menu, Role
from app.schemas.menus import MenuType
from app.settings.config import settings

from .middlewares import BackGroundTaskMiddleware, HttpAuditLogMiddleware


def make_middlewares():
    middleware = [
        Middleware(
            CORSMiddleware,
            allow_origins=settings.CORS_ORIGINS,
            allow_credentials=settings.CORS_ALLOW_CREDENTIALS,
            allow_methods=settings.CORS_ALLOW_METHODS,
            allow_headers=settings.CORS_ALLOW_HEADERS,
        ),
        Middleware(BackGroundTaskMiddleware),
        Middleware(GZipMiddleware, minimum_size=1024),
        Middleware(
            HttpAuditLogMiddleware,
            methods=["GET", "POST", "PUT", "DELETE"],
            exclude_paths=[
                "/api/v1/base/access_token",
                "/api/v1/skill/export",
                "/api/v1/workspace/sheet/upload",
                "/api/v1/workspace/document/upload",
                "/api/v1/workspace/document/download",
                "/api/v1/workspace/document/batch-export",
                "/api/v1/workspace/sheet/export",
                "/api/v1/workspace/sheet/batch-export",
                "/api/v1/workspace/analysis/export",
                "/api/v1/workspace/analysis/batch-export",
                "/api/v1/report/export/",
                "/api/v1/region/region-boundary/download-file",
                "/api/v1/region/road-network/download-file",
                "/api/v1/region/road-network/tiles/",
                "/api/v1/region/road-material/upload",
                "/api/v1/region/road-material/download-file",
                "/api/v1/workspace/static-file/upload",
                "/api/v1/workspace/static-file/batch-upload",
                "/api/v1/workspace/static-file/download-file",
                "/api/v1/workspace/static-file/batch-export",
                "/api/v1/workspace/sheet/batch-upload",
                "/api/v1/workspace/document/batch-upload",
                "/api/v1/i18n/export",
                "/api/v1/deploy/",
                "/api/s/",
                "/api/sf/",
                "/docs",
                "/openapi.json",
            ],
        ),
    ]
    return middleware


def register_exceptions(app: FastAPI):
    app.add_exception_handler(DoesNotExist, DoesNotExistHandle)
    app.add_exception_handler(HTTPException, HttpExcHandle)
    app.add_exception_handler(IntegrityError, IntegrityHandle)
    app.add_exception_handler(RequestValidationError, RequestValidationHandle)
    app.add_exception_handler(ResponseValidationError, ResponseValidationHandle)


def register_routers(app: FastAPI, prefix: str = "/api"):
    app.include_router(api_router, prefix=prefix)
    # 短链接公开访问 — 挂载在 /api/s 下，无鉴权，可被 Vite/Nginx 代理
    from app.api.v1.regions.road_material import short_router as road_material_short_router
    from app.api.v1.workspace.static_file import short_router as static_file_short_router
    app.include_router(road_material_short_router, prefix="/api/s", tags=["路网素材短链接"])
    app.include_router(static_file_short_router, prefix="/api/sf", tags=["静态文件短链接"])


def register_static(app: FastAPI):
    """[已弃用] 挂载前端静态文件（无需 Nginx）。仅在 web/dist/ 存在时生效。
    
    生产环境请使用 Nginx 托管前端静态文件并反向代理 /api/ 到 FastAPI，
    参见 deploy/web.conf。此处保留仅供本地开发调试使用。
    """
    import os
    from fastapi.staticfiles import StaticFiles

    static_dir = os.path.join(settings.BASE_DIR, "web", "dist")
    if os.path.isdir(static_dir):
        # html=True 实现 SPA fallback: 非 /api 路径 404 时返回 index.html
        app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")


async def init_superuser():
    user = await user_controller.model.exists()
    if not user:
        await user_controller.create_user(
            UserCreate(
                username="admin",
                email="admin@admin.com",
                password="123456",
                is_active=True,
                is_superuser=True,
            )
        )


async def init_menus():
    menus = await Menu.exists()
    if not menus:
        parent_menu = await Menu.create(
            menu_type=MenuType.CATALOG,
            name="系统管理",
            path="/system",
            order=1,
            parent_id=0,
            icon="carbon:gui-management",
            is_hidden=False,
            component="Layout",
            keepalive=False,
            redirect="/system/user",
        )
        children_menu = [
            Menu(
                menu_type=MenuType.MENU,
                name="用户管理",
                path="user",
                order=1,
                parent_id=parent_menu.id,
                icon="material-symbols:person-outline-rounded",
                is_hidden=False,
                component="/system/user",
                keepalive=False,
            ),
            Menu(
                menu_type=MenuType.MENU,
                name="角色管理",
                path="role",
                order=2,
                parent_id=parent_menu.id,
                icon="carbon:user-role",
                is_hidden=False,
                component="/system/role",
                keepalive=False,
            ),
            Menu(
                menu_type=MenuType.MENU,
                name="菜单管理",
                path="menu",
                order=3,
                parent_id=parent_menu.id,
                icon="material-symbols:list-alt-outline",
                is_hidden=False,
                component="/system/menu",
                keepalive=False,
            ),
            Menu(
                menu_type=MenuType.MENU,
                name="API管理",
                path="api",
                order=4,
                parent_id=parent_menu.id,
                icon="ant-design:api-outlined",
                is_hidden=False,
                component="/system/api",
                keepalive=False,
            ),
            Menu(
                menu_type=MenuType.MENU,
                name="国际化管理",
                path="i18n",
                order=5,
                parent_id=parent_menu.id,
                icon="carbon:translate",
                is_hidden=False,
                component="/system/i18n",
                keepalive=False,
            ),
            Menu(
                menu_type=MenuType.MENU,
                name="部门管理",
                path="dept",
                order=6,
                parent_id=parent_menu.id,
                icon="mingcute:department-line",
                is_hidden=False,
                component="/system/dept",
                keepalive=False,
            ),
            Menu(
                menu_type=MenuType.MENU,
                name="审计日志",
                path="auditlog",
                order=7,
                parent_id=parent_menu.id,
                icon="ph:clipboard-text-bold",
                is_hidden=False,
                component="/system/auditlog",
                keepalive=False,
            ),
            Menu(
                menu_type=MenuType.MENU,
                name="下载配置",
                path="/system/download-config",
                order=8,
                parent_id=0,
                icon="material-symbols:download",
                is_hidden=False,
                component="/system/download-config",
                keepalive=False,
            ),
        ]
        await Menu.bulk_create(children_menu)
        await Menu.create(
            menu_type=MenuType.MENU,
            name="一级菜单",
            path="/top-menu",
            order=2,
            parent_id=0,
            icon="material-symbols:featured-play-list-outline",
            is_hidden=False,
            component="/top-menu",
            keepalive=False,
            redirect="",
        )
        # 路网数据中心
        network_parent = await Menu.create(
            menu_type=MenuType.CATALOG,
            name="路网数据中心",
            path="/network",
            order=4,
            parent_id=0,
            icon="carbon:map-3",
            is_hidden=False,
            component="Layout",
            keepalive=False,
            redirect="/network/region",
        )
        await Menu.create(
            menu_type=MenuType.MENU,
            name="全球国家及行政区管理",
            path="region",
            order=1,
            parent_id=network_parent.id,
            icon="carbon:earth-filled",
            is_hidden=False,
            component="/network/region",
            keepalive=False,
        )
        await Menu.create(
            menu_type=MenuType.MENU,
            name="行政区边界文件管理",
            path="region-boundary",
            order=2,
            parent_id=network_parent.id,
            icon="carbon:map-boundary-vegetation",
            is_hidden=False,
            component="/network/region-boundary",
            keepalive=False,
        )
        await Menu.create(
            menu_type=MenuType.MENU,
            name="路网文件管理",
            path="road-network",
            order=3,
            parent_id=network_parent.id,
            icon="carbon:road",
            is_hidden=False,
            component="/network/road-network",
            keepalive=False,
        )
        await Menu.create(
            menu_type=MenuType.MENU,
            name="路网素材管理",
            path="road-material",
            order=4,
            parent_id=network_parent.id,
            icon="carbon:image-reference",
            is_hidden=False,
            component="/network/road-material",
            keepalive=False,
        )
        # 像素平台数据同步
        pixel_parent = await Menu.create(
            menu_type=MenuType.CATALOG,
            name="像素平台数据同步",
            path="/pixel",
            order=3,
            parent_id=0,
            icon="carbon:cloud-satellite-services",
            is_hidden=False,
            component="Layout",
            keepalive=False,
            redirect="/pixel/account",
        )
        await Menu.create(
            menu_type=MenuType.MENU,
            name="像素账户列表",
            path="account",
            order=1,
            parent_id=pixel_parent.id,
            icon="material-symbols:account-box-outline",
            is_hidden=False,
            component="/pixel/account",
            keepalive=False,
            redirect="",
        )


async def init_apis():
    apis = await api_controller.model.exists()
    if not apis:
        await api_controller.refresh_api()


async def init_db():
    command = Command(tortoise_config=settings.TORTOISE_ORM)
    try:
        await command.init_db(safe=True)
    except FileExistsError:
        pass

    await command.init()
    try:
        await command.migrate()
    except AttributeError:
        logger.warning("unable to retrieve model history from database, model history will be created from scratch")
        shutil.rmtree("migrations")
        await command.init_db(safe=True)

    await command.upgrade(run_in_transaction=True)


async def init_roles():
    roles = await Role.exists()
    if not roles:
        admin_role = await Role.create(
            name="管理员",
            desc="管理员角色",
        )
        user_role = await Role.create(
            name="普通用户",
            desc="普通用户角色",
        )

        # 分配所有API给管理员角色
        all_apis = await Api.all()
        await admin_role.apis.add(*all_apis)
        # 分配所有菜单给管理员和普通用户
        all_menus = await Menu.all()
        await admin_role.menus.add(*all_menus)
        await user_role.menus.add(*all_menus)

        # 为普通用户分配基本API
        basic_apis = await Api.filter(Q(method__in=["GET"]) | Q(tags="基础模块"))
        await user_role.apis.add(*basic_apis)


async def init_system_config():
    """初始化系统下载配置默认值"""
    try:
        from app.controllers.system_config import system_config_controller
        await system_config_controller.init_defaults()
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"系统配置初始化失败: {e}")


async def init_data():
    await init_db()
    await init_superuser()
    await init_menus()
    await init_apis()
    await init_roles()
    await init_system_config()
