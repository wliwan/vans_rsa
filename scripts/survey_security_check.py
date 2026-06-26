"""调研问卷安全审核脚本

检查 AI 生成的调查网页是否包含危险内容：
1. <script> 标签或事件处理中的 JS 代码
2. 文件读写操作引用
3. XSS 攻击向量
"""
import re
import sys
import json
from pathlib import Path


# ── 危险模式 ──

# ── 允许的安全模式（预处理时移除，再检查危险内容）──
ALLOWED_REMOVE = [
    # survey-lib.js 引用
    r'<\s*script\s+src=["\']/api/v1/survey/static/survey-lib\.js["\']\s*>\s*</\s*script\s*>',
    # __SURVEY_CONFIG__ 配置脚本
    r'<\s*script\s*>\s*window\.__SURVEY_CONFIG__\s*=\s*\{[^}]*\}\s*;\s*</\s*script\s*>',
    # HTML 注释
    r'<!--[\s\S]*?-->',
]

DANGEROUS_PATTERNS = [
    # ── <script> 标签（任何残留的都禁止）──
    (r"<\s*script[\s>]", "检测到禁止的 <script> 标签，问卷网页仅允许引用 survey-lib.js"),

    # ── 行内事件处理器 ──
    (r"\bon\w+\s*=", "检测到行内事件处理器(onclick/onload等)，问卷网页禁止JS代码"),

    # ── javascript: 协议 ──
    (r"javascript\s*:", "检测到 javascript: 协议，存在XSS风险"),

    # ── 文件读写 ──
    (r"\b(?:fs\.|require\s*\(\s*['\"]fs|open\s*\(\s*['\"][\/\w]|readFile|writeFile|createWriteStream|createReadStream|FileReader|Blob\()",
     "检测到文件读写操作，问卷网页禁止操作文件系统"),

    # ── eval / Function 构造函数 ──
    (r"\beval\s*\(|new\s+Function\s*\(", "检测到 eval/Function 动态代码执行"),

    # ── import / export ──
    (r"\bimport\s+[\{*]|\bexport\s+(?:default\s+)?(?:\{|class|function|const|let|var)",
     "检测到 import/export 模块语法"),

    # ── fetch / XMLHttpRequest / WebSocket ──
    (r"\bfetch\s*\(|XMLHttpRequest|WebSocket\s*\(", "检测到网络请求代码，问卷网页禁止主动发起网络请求"),

    # ── localStorage / sessionStorage / indexedDB（仅禁止写入，允许读取） ──
    (r"localStorage\.(?:setItem|removeItem|clear)\s*\(", "检测到 localStorage 写入操作"),
    (r"sessionStorage\.(?:setItem|removeItem|clear)\s*\(", "检测到 sessionStorage 写入操作"),

    # ── document.write ──
    (r"document\.write\s*\(", "检测到 document.write 调用"),

    # ── innerHTML 赋值 ──
    (r"\.innerHTML\s*=", "检测到 innerHTML 赋值，存在XSS风险"),
]


def check_html_file(filepath: str) -> dict:
    """检查HTML文件安全性

    Returns:
        {"passed": bool, "issues": list[str], "severity": str}
    """
    path = Path(filepath)
    if not path.exists():
        return {"passed": False, "issues": [f"文件不存在: {filepath}"], "severity": "error"}

    if path.suffix.lower() not in (".html", ".htm"):
        return {"passed": False, "issues": [f"不支持的文件类型: {path.suffix}"], "severity": "error"}

    try:
        content = path.read_text(encoding="utf-8")
    except Exception as e:
        return {"passed": False, "issues": [f"无法读取文件: {e}"], "severity": "error"}

    # 预处理：移除允许的安全模式
    sanitized = content
    for pattern in ALLOWED_REMOVE:
        sanitized = re.sub(pattern, "", sanitized, flags=re.IGNORECASE | re.DOTALL)

    issues = []
    for pattern, message in DANGEROUS_PATTERNS:
        matches = list(re.finditer(pattern, sanitized, re.IGNORECASE))
        for m in matches:
            # 找出所在行号（基于原始内容，方便定位）
            line_num = content[:m.start()].count("\n") + 1
            start = max(0, m.start() - 30)
            end = min(len(content), m.end() + 30)
            snippet = content[start:end].replace("\n", " ").strip()
            issues.append({
                "line": line_num,
                "message": message,
                "snippet": snippet[:100],
            })

    if issues:
        return {
            "passed": False,
            "issues": issues,
            "severity": "error",
            "detail": f"安全审核未通过：共发现 {len(issues)} 个安全问题",
        }

    return {
        "passed": True,
        "issues": [],
        "severity": "ok",
        "detail": "安全审核通过",
    }


def check_html_content(html_content: str) -> dict:
    """直接检查HTML内容字符串（不写文件）

    Returns:
        {"passed": bool, "issues": list[dict], "severity": str, "detail": str}
    """
    # 预处理：移除允许的安全模式
    sanitized = html_content
    for pattern in ALLOWED_REMOVE:
        sanitized = re.sub(pattern, "", sanitized, flags=re.IGNORECASE | re.DOTALL)

    issues = []

    for pattern, message in DANGEROUS_PATTERNS:
        matches = list(re.finditer(pattern, sanitized, re.IGNORECASE))
        for m in matches:
            line_num = html_content[:m.start()].count("\n") + 1
            start = max(0, m.start() - 30)
            end = min(len(html_content), m.end() + 30)
            snippet = html_content[start:end].replace("\n", " ").strip()
            issues.append({
                "line": line_num,
                "message": message,
                "snippet": snippet[:100],
            })

    if issues:
        return {
            "passed": False,
            "issues": issues,
            "severity": "error",
            "detail": f"安全审核未通过：共发现 {len(issues)} 个安全问题",
        }

    return {
        "passed": True,
        "issues": [],
        "severity": "ok",
        "detail": "安全审核通过",
    }


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(json.dumps({"passed": False, "issues": ["用法: python survey_security_check.py <html文件路径>"]}, ensure_ascii=False))
        sys.exit(1)

    result = check_html_file(sys.argv[1])
    print(json.dumps(result, ensure_ascii=False, indent=2))
    sys.exit(0 if result["passed"] else 1)
