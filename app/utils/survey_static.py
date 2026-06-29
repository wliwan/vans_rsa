"""问卷静态文件内容（读文件 + 缓存，更新文件后自动生效）"""
import os

_BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_LOCAL_DIR = os.path.join(_BASE, "uploads", "static_web")

# ── 缓存：按文件路径缓存内容 + mtime，5 秒内不重复读盘 ──
_cache: dict[str, tuple[float, str]] = {}
_CACHE_TTL = 5.0  # 秒


def _read_file_cached(filename: str) -> str | None:
    """读取文件内容（带 mtime 缓存），返回 None 表示文件不存在"""
    path = os.path.join(_LOCAL_DIR, filename)
    if not os.path.exists(path):
        return None
    mtime = os.path.getmtime(path)
    entry = _cache.get(path)
    if entry is not None:
        cached_mtime, cached_content = entry
        if cached_mtime == mtime:
            return cached_content
    with open(path, encoding="utf-8") as f:
        content = f.read()
    _cache[path] = (mtime, content)
    return content


def get_survey_lib_js() -> str:
    """获取 survey-lib.js 内容（优先读文件，文件缺失时抛错）"""
    content = _read_file_cached("survey-lib.js")
    if content is not None:
        return content
    raise FileNotFoundError(
        "survey-lib.js not found in uploads/static_web/. "
        "请将 survey-lib.js 放入 uploads/static_web/ 目录后重启服务。"
    )


def get_survey_lib_css() -> str:
    """获取 survey-lib.css 内容（优先读文件，文件缺失时抛错）"""
    content = _read_file_cached("survey-lib.css")
    if content is not None:
        return content
    raise FileNotFoundError(
        "survey-lib.css not found in uploads/static_web/. "
        "请将 survey-lib.css 放入 uploads/static_web/ 目录后重启服务。"
    )


# ── 向后兼容旧引用（模块级常量，延迟到首次访问时读盘） ──
class _LazyLoader:
    def __getattr__(self, name: str) -> str:
        if name == "SURVEY_LIB_JS":
            return get_survey_lib_js()
        if name == "SURVEY_LIB_CSS":
            return get_survey_lib_css()
        raise AttributeError(name)


import sys as __sys
__mod = __sys.modules[__name__]
__mod.__class__ = type(
    __mod.__class__.__name__,
    (__mod.__class__, _LazyLoader),
    {},
)
