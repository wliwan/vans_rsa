"""调研问卷安全审核

检查 AI 生成的调查网页是否包含危险内容：
1. <script> 标签或事件处理中的 JS 代码
2. 文件读写操作引用
3. XSS 攻击向量

注意：此模块与 scripts/survey_security_check.py 保持同步。
"""
import re
from pathlib import Path


# ── 允许的安全模式（预处理时移除，再检查危险内容）──
ALLOWED_REMOVE = [
    r'<\s*script\s+src=["\']/api/v1/survey/static/survey-lib\.js["\']\s*>\s*</\s*script\s*>',
    r'<\s*script\s*>\s*window\.__SURVEY_CONFIG__\s*=\s*\{[^}]*\}\s*;\s*</\s*script\s*>',
    r'<!--[\s\S]*?-->',
]

DANGEROUS_PATTERNS = [
    (r"javascript\s*:", "检测到 javascript: 协议"),
    (r"\b(?:fs\.|require\s*\(\s*['\"]fs|open\s*\(\s*['\"][\/\w]|readFile|writeFile|createWriteStream|createReadStream|FileReader|Blob\()",
     "检测到文件读写操作"),
    (r"\beval\s*\(|new\s+Function\s*\(", "检测到 eval/Function 动态代码执行"),
    (r"\bimport\s+[\{*]|\bexport\s+(?:default\s+)?(?:\{|class|function|const|let|var)",
     "检测到 import/export 模块语法"),
    (r"\bfetch\s*\(|XMLHttpRequest|WebSocket\s*\(", "检测到网络请求代码"),
    (r"localStorage\.(?:setItem|removeItem|clear)\s*\(", "检测到 localStorage 写入"),
    (r"sessionStorage\.(?:setItem|removeItem|clear)\s*\(", "检测到 sessionStorage 写入"),
    (r"document\.write\s*\(", "检测到 document.write 调用"),
    (r"\.innerHTML\s*=", "检测到 innerHTML 赋值"),
    (r"\.outerHTML\s*=", "检测到 outerHTML 赋值"),

    # ── 数据外泄渠道 ──
    (r"\bnavigator\.sendBeacon\s*\(", "检测到 sendBeacon 调用（疑似数据外泄）"),
    (r"\bnew\s+Image\s*\([^)]*\)\s*\.\s*src\s*=", "检测到 Image.src 赋值（疑似数据外泄）"),

    # ── 页面劫持/重定向 ──
    (r"\blocation\s*\.\s*(?:href|replace|assign)\s*=", "检测到 location 重定向"),
    (r"\bwindow\s*\.\s*open\s*\(", "检测到 window.open 调用"),

    # ── 动态执行/加载 ──
    (r"\bsetTimeout\s*\(\s*['\"]", "检测到 setTimeout 字符串参数（隐式 eval）"),
    (r"\bsetInterval\s*\(\s*['\"]", "检测到 setInterval 字符串参数（隐式 eval）"),
    (r"createElement\s*\(\s*['\"]script['\"]", "检测到动态创建 script 标签"),
]


def check_html_content(html_content: str) -> dict:
    """检查 HTML 内容安全性"""
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
    return {"passed": True, "issues": [], "severity": "ok", "detail": "安全审核通过"}
