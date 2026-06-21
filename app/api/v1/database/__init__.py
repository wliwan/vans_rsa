"""
数据库数据导入 API
提供 MySQL / SQLite / 像素平台 / 路网数据的导入接口
"""
import logging
import os

from fastapi import APIRouter, File, Query, UploadFile
from tortoise.expressions import Q

from app.controllers.workspace import DatabaseImportService, workspace_controller
from app.core.ctx import CTX_USER_ID
from app.models.admin import Document
from app.schemas.base import Fail, Success, SuccessExtra
from app.schemas.workspace import *
from app.settings.config import settings

logger = logging.getLogger(__name__)

router = APIRouter()


def _check_workspace(workspace_id: int, user_id: int):
    """检查工作区权限的辅助函数"""
    return workspace_controller.check_permission(workspace_id, user_id)


# ==================== MySQL ====================

@router.post("/mysql/test-connection", summary="测试 MySQL 连接")
async def test_mysql_connection(req: MySQLConnectRequest):
    try:
        tables = await DatabaseImportService.mysql_list_tables(
            host=req.host, port=req.port, user=req.user,
            password=req.password, database=req.database,
        )
        return Success(data={"tables": tables}, msg=f"连接成功，共 {len(tables)} 个表")
    except ImportError:
        return Fail(code=500, msg="请安装 pymysql 依赖: pip install pymysql")
    except Exception as e:
        logger.error(f"MySQL 连接测试失败: {e}")
        return Fail(code=500, msg=f"连接失败: {str(e)}")


@router.post("/mysql/import", summary="从 MySQL 导入数据表")
async def import_mysql_tables(req: MySQLImportRequest):
    user_id = CTX_USER_ID.get()
    ws = await _check_workspace(req.workspace_id, user_id)
    if not ws:
        return Fail(code=403, msg="无权操作该工作区")
    try:
        docs = await DatabaseImportService.mysql_import_tables(
            workspace_id=req.workspace_id,
            host=req.host, port=req.port, user=req.user,
            password=req.password, database=req.database,
            tables=req.tables,
        )
        return Success(data=docs, msg=f"成功导入 {len(docs)} 个表")
    except ImportError:
        return Fail(code=500, msg="请安装 pymysql 依赖: pip install pymysql")
    except Exception as e:
        logger.error(f"MySQL 导入失败: {e}")
        return Fail(code=500, msg=f"导入失败: {str(e)}")


# ==================== SQLite ====================

@router.post("/sqlite/upload", summary="上传 SQLite 文件并列出表")
async def upload_sqlite_file(
    workspace_id: int = Query(..., description="工作区ID"),
    file: UploadFile = File(..., description="SQLite文件"),
):
    user_id = CTX_USER_ID.get()
    ws = await _check_workspace(workspace_id, user_id)
    if not ws:
        return Fail(code=403, msg="无权操作该工作区")

    if not file.filename or not file.filename.endswith((".sqlite", ".sqlite3", ".db")):
        return Fail(code=400, msg="仅支持 .sqlite / .sqlite3 / .db 格式")

    # 保存文件到 uploads 目录
    upload_dir = os.path.join(settings.BASE_DIR, "uploads", "sqlite")
    os.makedirs(upload_dir, exist_ok=True)
    import uuid
    unique_name = f"{uuid.uuid4().hex}_{file.filename}"
    file_path = os.path.join(upload_dir, unique_name)
    content = await file.read()
    with open(file_path, "wb") as f:
        f.write(content)

    try:
        tables = await DatabaseImportService.sqlite_list_tables(file_path)
        return Success(data={
            "file_path": file_path,
            "file_name": file.filename,
            "tables": tables,
        }, msg=f"上传成功，共 {len(tables)} 个表")
    except Exception as e:
        logger.error(f"SQLite 解析失败: {e}")
        return Fail(code=500, msg=f"解析失败: {str(e)}")


@router.post("/sqlite/import", summary="从 SQLite 导入数据表")
async def import_sqlite_tables(req: SQLiteImportRequest):
    user_id = CTX_USER_ID.get()
    ws = await _check_workspace(req.workspace_id, user_id)
    if not ws:
        return Fail(code=403, msg="无权操作该工作区")
    if not os.path.exists(req.file_path):
        return Fail(code=400, msg="SQLite 文件不存在，请重新上传")
    try:
        docs = await DatabaseImportService.sqlite_import_tables(
            workspace_id=req.workspace_id,
            file_path=req.file_path,
            tables=req.tables,
        )
        return Success(data=docs, msg=f"成功导入 {len(docs)} 个表")
    except Exception as e:
        logger.error(f"SQLite 导入失败: {e}")
        return Fail(code=500, msg=f"导入失败: {str(e)}")


# ==================== 像素平台 ====================

@router.get("/pixel/accounts", summary="获取用户可访问的像素账户列表")
async def list_pixel_accounts():
    user_id = CTX_USER_ID.get()
    try:
        accounts = await DatabaseImportService.pixel_list_accounts(user_id)
        return Success(data=accounts)
    except Exception as e:
        logger.error(f"获取像素账户失败: {e}")
        return Fail(code=500, msg=str(e))


@router.get("/pixel/tables", summary="获取像素平台数据表列表")
async def list_pixel_tables(
    pixel_account_id: int = Query(..., description="像素账户ID"),
):
    user_id = CTX_USER_ID.get()
    try:
        tables = await DatabaseImportService.pixel_list_tables(pixel_account_id, user_id)
        return Success(data=tables)
    except ValueError as e:
        return Fail(code=400, msg=str(e))
    except Exception as e:
        logger.error(f"获取像素数据表失败: {e}")
        return Fail(code=500, msg=str(e))


@router.post("/pixel/import", summary="从像素平台导入数据表")
async def import_pixel_table(req: PixelImportRequest):
    user_id = CTX_USER_ID.get()
    ws = await _check_workspace(req.workspace_id, user_id)
    if not ws:
        return Fail(code=403, msg="无权操作该工作区")
    try:
        doc = await DatabaseImportService.pixel_import_table(
            workspace_id=req.workspace_id,
            pixel_account_id=req.pixel_account_id,
            table_name=req.table_name,
            table_label=req.table_label,
            user_id=user_id,
        )
        return Success(data=doc, msg="导入成功")
    except ValueError as e:
        return Fail(code=400, msg=str(e))
    except Exception as e:
        logger.error(f"像素数据导入失败: {e}")
        return Fail(code=500, msg=f"导入失败: {str(e)}")


# ==================== 路网数据 ====================

@router.get("/road-network/regions", summary="获取有路网数据的区域列表")
async def list_road_network_regions():
    try:
        regions = await DatabaseImportService.road_network_list_regions()
        return Success(data=regions)
    except Exception as e:
        logger.error(f"获取路网区域失败: {e}")
        return Fail(code=500, msg=str(e))


@router.get("/road-network/list", summary="获取区域下的路网文件列表")
async def list_road_networks(
    region_id: int = Query(..., description="区域ID"),
):
    try:
        networks = await DatabaseImportService.road_network_list_for_region(region_id)
        return Success(data=networks)
    except Exception as e:
        logger.error(f"获取路网列表失败: {e}")
        return Fail(code=500, msg=str(e))


@router.post("/road-network/import", summary="从路网数据导入统计")
async def import_road_network_stats(req: RoadNetworkImportRequest):
    user_id = CTX_USER_ID.get()
    ws = await _check_workspace(req.workspace_id, user_id)
    if not ws:
        return Fail(code=403, msg="无权操作该工作区")
    try:
        docs = await DatabaseImportService.road_network_import_stats(
            workspace_id=req.workspace_id,
            region_id=req.region_id,
            road_network_ids=req.road_network_ids,
        )
        return Success(data=docs, msg=f"成功导入 {len(docs)} 个路网统计")
    except Exception as e:
        logger.error(f"路网导入失败: {e}")
        return Fail(code=500, msg=f"导入失败: {str(e)}")
