"""调研问卷 API 路由"""
import os
from typing import List, Optional

from fastapi import APIRouter, Query
from fastapi.responses import FileResponse, HTMLResponse, Response

from app.controllers.survey import SURVEY_WEB_DIR, survey_controller
from app.utils.survey_static import SURVEY_LIB_JS, SURVEY_LIB_CSS
from app.core.ctx import CTX_USER_ID
from app.log import logger
from app.schemas.base import Fail, Success, SuccessExtra
from app.schemas.survey import SurveyCreate, SurveySubmissionCreate, SurveyUpdate
from app.settings.config import settings

survey_router = APIRouter()
survey_public_router = APIRouter()  # 公开接口，无需鉴权


# ═══════════════════════════════════════
#  问卷 CRUD（需鉴权）
# ═══════════════════════════════════════

@survey_router.get("/list", summary="获取问卷列表")
async def list_surveys(
    page: int = Query(1, description="页码", ge=1),
    page_size: int = Query(50, description="每页数量", ge=1, le=100),
):
    user_id = CTX_USER_ID.get()
    total, data = await survey_controller.list_accessible(user_id, page, page_size)
    return SuccessExtra(data=data, total=total, page=page, page_size=page_size)


@survey_router.get("/get", summary="获取问卷详情")
async def get_survey(survey_id: int = Query(..., description="问卷ID")):
    obj = await survey_controller.get(id=survey_id)
    if not obj:
        return Fail(code=404, msg="问卷不存在")
    return Success(data=survey_controller._to_output(obj))


@survey_router.post("/create", summary="AI创建问卷")
async def create_survey(obj_in: SurveyCreate):
    """通过 AI 生成问卷网页，风险评估后保存（不拦截）"""
    user_id = CTX_USER_ID.get()
    try:
        result = await survey_controller.create_with_ai(obj_in, creator_id=user_id)
        return Success(data=result, msg=result.get("message", "问卷创建成功"))
    except ValueError as e:
        return Fail(code=400, msg=str(e))
    except Exception as e:
        logger.exception("创建问卷失败")
        return Fail(code=500, msg=f"创建问卷失败: {str(e)}")


@survey_router.post("/update", summary="更新问卷")
async def update_survey(obj_in: SurveyUpdate):
    result = await survey_controller.update_survey(obj_in.id, obj_in)
    if not result:
        return Fail(code=404, msg="问卷不存在")
    return Success(data=result, msg="更新成功")


@survey_router.delete("/delete", summary="删除问卷")
async def delete_survey(survey_id: int = Query(..., description="问卷ID")):
    ok = await survey_controller.delete_survey(survey_id)
    if not ok:
        return Fail(code=404, msg="问卷不存在")
    return Success(msg="删除成功")


# ═══════════════════════════════════════
#  问卷提交记录（需鉴权）
# ═══════════════════════════════════════

@survey_router.get("/submissions", summary="获取问卷提交记录")
async def list_submissions(
    survey_id: int = Query(..., description="问卷ID"),
    page: int = Query(1, description="页码", ge=1),
    page_size: int = Query(50, description="每页数量", ge=1, le=100),
    save_type: Optional[str] = Query(None, description="保存类型: save / submit"),
):
    total, data = await survey_controller.list_submissions(
        survey_id, page, page_size, save_type,
    )
    return SuccessExtra(data=data, total=total, page=page, page_size=page_size)


@survey_router.delete("/submission/delete", summary="删除提交记录")
async def delete_submission(submission_id: int = Query(..., description="提交记录ID")):
    ok = await survey_controller.delete_submission(submission_id)
    if not ok:
        return Fail(code=404, msg="提交记录不存在")
    return Success(msg="删除成功")


@survey_router.get("/html", summary="获取问卷HTML内容（用于预览）")
async def get_survey_html(survey_id: int = Query(..., description="问卷ID")):
    html = await survey_controller.get_survey_html(survey_id)
    if not html:
        return Fail(code=404, msg="问卷网页文件不存在")
    return Success(data={"html": html})


@survey_router.get("/risk", summary="查看问卷风险信息")
async def get_survey_risk(survey_id: int = Query(..., description="问卷ID")):
    """查看已有问卷的风险评估信息（只读）"""
    try:
        result = await survey_controller.get_risk_info(survey_id)
        return Success(data=result, msg="风险评估信息")
    except ValueError as e:
        return Fail(code=400, msg=str(e))
    except Exception as e:
        logger.exception("获取风险信息失败")
        return Fail(code=500, msg=f"获取风险信息失败: {str(e)}")


# ═══════════════════════════════════════
#  短链接访问（无需鉴权）— 独立 router
# ═══════════════════════════════════════

short_router = APIRouter()


@short_router.get("/{token}", summary="通过短链接访问问卷网页")
async def access_survey_by_short_token(token: str):
    """问卷短链接访问，无需登录，直接返回 HTML 网页"""
    survey = await survey_controller.get_by_short_token(token)
    if not survey or not survey.file_path:
        return HTMLResponse(
            content="<h1>问卷不存在或已失效</h1><p>请联系问卷创建者。</p>",
            status_code=404,
        )
    if not os.path.exists(survey.file_path):
        return HTMLResponse(
            content="<h1>问卷文件丢失</h1><p>请联系管理员。</p>",
            status_code=404,
        )
    return FileResponse(
        survey.file_path,
        media_type="text/html; charset=utf-8",
    )


# ═══════════════════════════════════════
#  问卷提交（无需鉴权）— 公开接口
# ═══════════════════════════════════════

@survey_public_router.post("/submit", summary="提交问卷数据（公开接口，无需鉴权）")
async def submit_survey(obj_in: SurveySubmissionCreate):
    """用户通过问卷网页提交数据，无需登录"""
    try:
        result = await survey_controller.create_submission(obj_in)
        return Success(data=result, msg="提交成功")
    except ValueError as e:
        return Fail(code=400, msg=str(e))
    except Exception as e:
        logger.exception("问卷提交失败")
        return Fail(code=500, msg=f"提交失败: {str(e)}")


# ═══════════════════════════════════════
#  通用库文件访问（无需鉴权）
# ═══════════════════════════════════════

@survey_public_router.get("/static/survey-lib.js", summary="获取问卷通用JS库")
async def get_survey_lib_js():
    """返回问卷通用 JS 库（无需鉴权，问卷网页引用）"""
    return Response(content=SURVEY_LIB_JS, media_type="application/javascript; charset=utf-8")


@survey_public_router.get("/static/survey-lib.css", summary="获取问卷通用CSS库")
async def get_survey_lib_css():
    """返回问卷通用 CSS 库（无需鉴权，问卷网页引用）"""
    return Response(content=SURVEY_LIB_CSS, media_type="text/css; charset=utf-8")
