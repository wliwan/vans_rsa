"""
热更新 — 上传 zip 直接替换容器内前端 / 后端代码。

适用场景：不想重建整个 Docker 镜像，快速迭代。
"""

import asyncio
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile

from fastapi import APIRouter, File, UploadFile

from app.schemas.base import Success, Fail

# 容器内前端 dist 根目录（由 Dockerfile COPY 而来，与 Nginx root 一致）
DIST_ROOT = "/opt/VansRSA/web/dist"
# 容器内后端代码根目录
BACKEND_ROOT = "/opt/VansRSA/app"
BACKEND_BACKUP = "/opt/VansRSA/app_backup"

router = APIRouter()


@router.post("/update-frontend", summary="上传前端 zip 更新包，热替换容器内 dist/")
async def update_frontend(
    file: UploadFile = File(..., description="前端构建产物 zip 包")
):
    """接收 zip 包，解压后替换 Nginx 静态文件目录，实现零停机前端更新。"""
    # 1. 校验文件名
    if not file.filename or not file.filename.lower().endswith(".zip"):
        return Fail(code=400, msg="仅支持 .zip 格式")

    # 2. 读取文件内容
    zip_bytes = await file.read()
    file_size_mb = len(zip_bytes) / (1024 * 1024)
    if len(zip_bytes) == 0:
        return Fail(code=400, msg="上传文件为空")

    # 3. 写入临时文件并解压
    tmp_dir = tempfile.mkdtemp(prefix="frontend-update-")
    zip_path = os.path.join(tmp_dir, "dist.zip")
    extract_dir = os.path.join(tmp_dir, "extracted")

    try:
        with open(zip_path, "wb") as f:
            f.write(zip_bytes)

        # 校验是有效 zip
        if not zipfile.is_zipfile(zip_path):
            return Fail(code=400, msg="文件不是有效的 zip 包")

        # 解压
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(extract_dir)

        # 查找解压后的 dist 目录（允许 zip 内有一层包装目录如 dist/）
        dist_src = _find_dist_dir(extract_dir)
        if dist_src is None:
            return Fail(code=400, msg="zip 包中未找到 dist/ 目录或 index.html")

        # 验证 index.html 存在
        if not os.path.isfile(os.path.join(dist_src, "index.html")):
            return Fail(code=400, msg="zip 包中 dist/ 目录缺少 index.html")

        # 统计文件
        file_count = sum(1 for _ in _walk_files(dist_src))

        # 4. 替换目标目录
        _replace_dir(dist_src, DIST_ROOT)

        return Success(
            data={
                "file_count": file_count,
                "size_mb": round(file_size_mb, 2),
                "target": DIST_ROOT,
            },
            msg=f"前端已更新（{file_count} 个文件, {file_size_mb:.1f} MB），Nginx 即时生效",
        )

    finally:
        # 5. 清理临时文件
        shutil.rmtree(tmp_dir, ignore_errors=True)


def _find_dist_dir(base: str):
    """在解压目录中查找真正的 dist 目录。

    zip 可能是两种结构：
      A) dist/index.html, dist/assets/...          → 直接有 dist/
      B) frontend-update/dist/index.html, ...       → 有一层外层目录
    """
    # 先看是否有 dist/
    dist_path = os.path.join(base, "dist")
    if os.path.isdir(dist_path) and os.path.isfile(os.path.join(dist_path, "index.html")):
        return dist_path

    # 再看 index.html 是否在根
    if os.path.isfile(os.path.join(base, "index.html")):
        return base

    # 遍历一层子目录
    for name in os.listdir(base):
        sub = os.path.join(base, name)
        if not os.path.isdir(sub):
            continue
        # 子目录下有 dist/
        dist_path = os.path.join(sub, "dist")
        if os.path.isdir(dist_path) and os.path.isfile(os.path.join(dist_path, "index.html")):
            return dist_path
        # 子目录本身就是类 dist 结构
        if os.path.isfile(os.path.join(sub, "index.html")) and _has_assets(sub):
            return sub

    return None


def _has_assets(path):
    return os.path.isdir(os.path.join(path, "assets"))


def _walk_files(root: str):
    for dirpath, _, filenames in os.walk(root):
        for fn in filenames:
            yield os.path.join(dirpath, fn)


def _replace_dir(src: str, dst: str):
    """用 src 内容替换 dst 目录。先清空 dst，再复制 src 下所有内容到 dst。"""
    os.makedirs(dst, exist_ok=True)

    for name in os.listdir(dst):
        path = os.path.join(dst, name)
        if os.path.isdir(path) and not os.path.islink(path):
            shutil.rmtree(path, ignore_errors=True)
        else:
            os.unlink(path)

    for name in os.listdir(src):
        s = os.path.join(src, name)
        d = os.path.join(dst, name)
        if os.path.isdir(s):
            shutil.copytree(s, d, symlinks=True)
        else:
            shutil.copy2(s, d)


# ═══════════════════════════════════════════════════════
# 后端热更新
# ═══════════════════════════════════════════════════════

@router.post("/update-backend", summary="上传后端 zip 更新包，覆盖代码并重启服务")
async def update_backend(
    file: UploadFile = File(..., description="后端代码 zip 包（含 app/ 目录）")
):
    """接收后端 zip，语法验证 → 备份旧代码 → 覆盖 → 容器自动重启。

    安全措施：
      - 解压后编译检查关键 Python 文件，防止语法错误导致启动失败
      - 旧代码备份到 /opt/VansRSA/app_backup/（仅保留最近一次）
      - 响应返回后才触发退出，确保客户端收到确认
    """
    if not file.filename or not file.filename.lower().endswith(".zip"):
        return Fail(code=400, msg="仅支持 .zip 格式")

    zip_bytes = await file.read()
    if len(zip_bytes) == 0:
        return Fail(code=400, msg="上传文件为空")

    tmp_dir = tempfile.mkdtemp(prefix="backend-update-")
    zip_path = os.path.join(tmp_dir, "backend.zip")
    extract_dir = os.path.join(tmp_dir, "extracted")

    try:
        # 1. 写入并解压
        with open(zip_path, "wb") as f:
            f.write(zip_bytes)

        if not zipfile.is_zipfile(zip_path):
            return Fail(code=400, msg="文件不是有效的 zip 包")

        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(extract_dir)

        # 2. 查找 app/ 目录
        app_src = _find_app_dir(extract_dir)
        if app_src is None:
            return Fail(code=400, msg="zip 包中未找到 app/ 目录（需包含 __init__.py 等文件）")

        # 3. Python 语法检查
        syntax_errors = _check_python_syntax(app_src)
        if syntax_errors:
            return Fail(code=400, msg=f"代码语法错误，拒绝更新:\n{chr(10).join(syntax_errors[:10])}")

        # 4. 备份旧代码
        if os.path.exists(BACKEND_ROOT):
            if os.path.exists(BACKEND_BACKUP):
                shutil.rmtree(BACKEND_BACKUP, ignore_errors=True)
            shutil.copytree(BACKEND_ROOT, BACKEND_BACKUP, symlinks=True)

        # 5. 覆盖代码
        _replace_dir(app_src, BACKEND_ROOT)

        file_count = sum(1 for _ in _walk_files(app_src))
        size_mb = len(zip_bytes) / (1024 * 1024)

        # 5.5. 安装依赖（如果 zip 中包含 requirements.txt）
        req_file = _find_requirements_file(extract_dir, app_src)
        if req_file:
            try:
                result = subprocess.run(
                    [sys.executable, "-m", "pip", "install", "-r", req_file,
                     "-i", "https://pypi.tuna.tsinghua.edu.cn/simple"],
                    capture_output=True, text=True, timeout=120,
                )
                if result.returncode != 0:
                    return Fail(code=500, msg=f"依赖安装失败: {result.stderr[-500:]}")
            except subprocess.TimeoutExpired:
                return Fail(code=500, msg="依赖安装超时（120s）")

        # 6. 延迟退出（给客户端响应时间）
        async def _delayed_restart():
            await asyncio.sleep(2)
            sys.exit(0)

        asyncio.create_task(_delayed_restart())

        return Success(
            data={
                "file_count": file_count,
                "size_mb": round(size_mb, 2),
                "backup": BACKEND_BACKUP,
            },
            msg=f"后端已更新（{file_count} 个文件），服务将在 2 秒后重启（容器自动拉起）",
        )

    except Exception as e:
        return Fail(code=500, msg=f"更新失败: {str(e)}")

    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def _find_app_dir(base: str) -> str | None:
    """在解压目录中查找 app/ 目录。支持：
      - 直接有 app/
      - 外层目录/app/
      - 直接是代码文件（无 app 目录，如 run.py + controllers/）
    """
    # 直接有 app/
    direct = os.path.join(base, "app")
    if os.path.isdir(direct) and os.path.isfile(os.path.join(direct, "__init__.py")):
        return direct

    # 直接就是代码（有 run.py 或 controllers/ 等）
    if os.path.isfile(os.path.join(base, "run.py")) or os.path.isdir(os.path.join(base, "controllers")):
        return base

    # 遍历一层子目录
    for name in os.listdir(base):
        sub = os.path.join(base, name)
        if not os.path.isdir(sub):
            continue
        # 子目录下 app/
        app_path = os.path.join(sub, "app")
        if os.path.isdir(app_path) and os.path.isfile(os.path.join(app_path, "__init__.py")):
            return app_path
        # 子目录就是代码根
        if os.path.isfile(os.path.join(sub, "run.py")) or os.path.isdir(os.path.join(sub, "controllers")):
            return sub

    return None


def _find_requirements_file(extract_dir: str, app_dir: str) -> str | None:
    """在解压目录中查找 requirements.txt（可能和 app/ 同级或在外层目录）"""
    # 和外层目录同级
    parent = os.path.dirname(app_dir.rstrip("/")) if app_dir != extract_dir else extract_dir
    req_path = os.path.join(parent, "requirements.txt")
    if os.path.isfile(req_path):
        return req_path
    # extract_dir 根
    req_path = os.path.join(extract_dir, "requirements.txt")
    if os.path.isfile(req_path):
        return req_path
    # 遍历一层
    for name in os.listdir(extract_dir):
        sub = os.path.join(extract_dir, name)
        candidate = os.path.join(sub, "requirements.txt")
        if os.path.isdir(sub) and os.path.isfile(candidate):
            return candidate
    return None


def _check_python_syntax(app_dir: str) -> list[str]:
    """编译检查 app/ 下所有 .py 文件语法，返回错误列表。"""
    errors = []
    for dirpath, _, filenames in os.walk(app_dir):
        for fn in filenames:
            if not fn.endswith(".py"):
                continue
            filepath = os.path.join(dirpath, fn)
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    source = f.read()
                compile(source, filepath, "exec")
            except SyntaxError as e:
                rel = os.path.relpath(filepath, app_dir)
                errors.append(f"{rel}:{e.lineno}: {e.msg}")
            except Exception as e:
                rel = os.path.relpath(filepath, app_dir)
                errors.append(f"{rel}: {e}")
    return errors
