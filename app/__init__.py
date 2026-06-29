from contextlib import asynccontextmanager

from fastapi import FastAPI
from tortoise import Tortoise

from app.core.exceptions import SettingNotFound
from app.core.init_app import (
    init_data,
    make_middlewares,
    register_exceptions,
    register_routers,
)

try:
    from app.settings.config import settings
except ImportError:
    raise SettingNotFound("Can not import settings")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_data()
    yield
    await Tortoise.close_connections()


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.APP_TITLE,
        description=settings.APP_DESCRIPTION,
        version=settings.VERSION,
        openapi_url="/openapi.json",
        middleware=make_middlewares(),
        lifespan=lifespan,
    )
    register_exceptions(app)
    register_routers(app, prefix="/api")
    # register_static(app)  # 前端静态文件由 Nginx 托管，此处注释掉

    # 确保问卷静态文件存在（不受 register_static 注释影响）
    import os as _os
    from app.core.init_app import _ensure_survey_static_files as _ensure_survey
    _survey_dir = _os.path.join(settings.BASE_DIR, "uploads", "static_web")
    _ensure_survey(_survey_dir)

    return app


app = create_app()
