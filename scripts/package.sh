#!/bin/bash
# ============================================================
# vue-fastapi-admin 项目打包脚本
#
# 用途: 将项目源码打包为 zip，方便拷贝到 Windows 上
#        通过 Docker Compose 一键部署。
#
# 用法: bash package.sh
# 输出: dist_package/vue-fastapi-admin_YYYYMMDD_HHMMSS.zip
# ============================================================

set -e

# ── 基本变量 ────────────────────────────────────────────────
PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_NAME="VansRSA"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
ZIP_NAME="${PROJECT_NAME}_${TIMESTAMP}.zip"
OUTPUT_DIR="${PROJECT_DIR}/dist_package"

echo "============================================"
echo "  ${PROJECT_NAME} 打包脚本"
echo "============================================"
echo ""
echo "  输出: ${OUTPUT_DIR}/${ZIP_NAME}"
echo ""

# ── 创建输出目录 ────────────────────────────────────────────
mkdir -p "${OUTPUT_DIR}"

# ── 切换到项目根目录 ────────────────────────────────────────
cd "${PROJECT_DIR}"

# ── 打包 ────────────────────────────────────────────────────
# -r  递归目录
# -q  安静模式（减少输出）
# -x  排除模式（支持通配符）
zip -rq "${OUTPUT_DIR}/${ZIP_NAME}" . \
    -x ".git/*" \
    -x "*/.git/*" \
    -x "*/__pycache__/*" \
    -x "*.pyc" \
    -x ".venv/*" \
    -x "venv/*" \
    -x ".idea/*" \
    -x ".vscode/*" \
    -x ".vscode-shared/*" \
    -x ".mypy_cache/*" \
    -x ".ruff_cache/*" \
    -x ".pytest_cache/*" \
    -x "*/node_modules/*" \
    -x "migrations/models/__pycache__/*" \
    -x "cache/*" \
    -x "uploads/*" \
    -x "db.sqlite3" \
    -x "db.sqlite3-*" \
    -x "data/db.sqlite3" \
    -x "data/db.sqlite3-*" \
    -x ".DS_Store" \
    -x "._.DS_Store" \
    -x ".codewhale/*" \
    -x "dist_package/*" \
    -x "*.zip" \
    -x "app/logs/*" \
    -x ".npm/*" \
    -x ".cache/*" \
    -x ".local/*" \
    -x ".config/*" \
    -x ".mozilla/*" \
    -x ".dotnet/*" \
    -x ".copilot/*" \
    -x ".nv/*" \
    -x ".pki/*" \
    -x ".var/*" \
    -x ".bash*" \
    -x ".wget-hsts" \
    -x ".zprofile" \
    -x ".zshrc" \
    -x ".nvidia*" \
    -x "downloads/*" \
    -x "公共/*" \
    -x "图片/*" \
    -x "文档/*" \
    -x "桌面/*" \
    -x "模板/*" \
    -x "视频/*" \
    -x "音乐/*" \
    -x "App/*" \
    -x "Dev/*"

# ── 输出结果 ────────────────────────────────────────────────
FILE_SIZE="$(du -h "${OUTPUT_DIR}/${ZIP_NAME}" | cut -f1)"

echo ""
echo "============================================"
echo "  打包完成！"
echo "============================================"
echo "  文件 : ${OUTPUT_DIR}/${ZIP_NAME}"
echo "  大小 : ${FILE_SIZE}"
echo ""
echo "  Windows 部署步骤:"
echo "  1. 将 ${ZIP_NAME} 复制到 Windows 机器"
echo "  2. 解压到目标目录"
echo "  3. 在解压目录打开终端 (PowerShell / CMD)"
echo "  4. docker compose up -d"
echo "  5. 访问 http://localhost:1110"
echo "     username: admin"
echo "     password: 123456"
echo "============================================"
