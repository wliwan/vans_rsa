"""
前端热更新 — 上传 zip 直接替换容器内编译产物。

适用场景：后端未变，只改了前端代码，不想重建整个 Docker 镜像。
"""

import os
import shutil
import tempfile
import zipfile

from fastapi import APIRouter, File, UploadFile

from app.schemas.base import Success, Fail

# 容器内前端 dist 根目录（由 Dockerfile COPY 而来，与 Nginx root 一致）
DIST_ROOT = "/opt/VansRSA/web/dist"

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
    # 确保目标目录存在
    os.makedirs(dst, exist_ok=True)

    # 清空目标目录
    for name in os.listdir(dst):
        path = os.path.join(dst, name)
        if os.path.isdir(path) and not os.path.islink(path):
            shutil.rmtree(path, ignore_errors=True)
        else:
            os.unlink(path)

    # 复制 src 内容到 dst
    for name in os.listdir(src):
        s = os.path.join(src, name)
        d = os.path.join(dst, name)
        if os.path.isdir(s):
            shutil.copytree(s, d, symlinks=True)
        else:
            shutil.copy2(s, d)
