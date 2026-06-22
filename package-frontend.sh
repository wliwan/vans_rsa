#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────
# VansRSA 前端打包脚本
#
# 构建前端，打包成 zip。然后通过管理后台 API 上传即可热更新。
#
# 用法:
#   ./package-frontend.sh                      # 构建并打包
#   ./package-frontend.sh --no-build           # 跳过构建，用已有 dist/
#   ./package-frontend.sh -o my-update.zip     # 指定输出文件名
#
# 输出:
#   dist_package/frontend-update-YYYYMMDD-HHMMSS.zip
#
# 上传方式:
#   管理后台 → 前端热更新 → 选择 zip 上传
#   或 POST /api/v1/deploy/update-frontend
# ──────────────────────────────────────────────────────────

set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

# ── 默认值 ──
WEB_DIR="${WEB_DIR:-$ROOT/web}"
DIST_DIR="${DIST_DIR:-$WEB_DIR/dist}"
OUTPUT_DIR="$ROOT/dist_package"
BUILD=true
OUTPUT_NAME=""

# ── 颜色 ──
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'
step()  { echo -e "${CYAN}➜ $*${NC}"; }
ok()    { echo -e "${GREEN}✔ $*${NC}"; }
warn()  { echo -e "${YELLOW}⚠ $*${NC}"; }
err()   { echo -e "${RED}✘ $*${NC}"; }

usage() {
  echo "用法: $0 [选项]"
  echo ""
  echo "选项:"
  echo "  --no-build          跳过构建，用已有 dist/"
  echo "  -o, --output FILE   指定输出文件名（默认: frontend-update-时间戳.zip）"
  echo "  -h, --help          显示帮助"
  exit 0
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --no-build) BUILD=false; shift ;;
    -o|--output) OUTPUT_NAME="$2"; shift 2 ;;
    -h|--help) usage ;;
    *) err "未知选项: $1"; usage ;;
  esac
done

# ── 时间戳 ──
TIMESTAMP=$(date +%Y%m%d-%H%M%S)
if [ -z "$OUTPUT_NAME" ]; then
  OUTPUT_NAME="frontend-update-${TIMESTAMP}.zip"
fi

# ──────────────────────────────────────────────────────────
# 1. 构建前端
# ──────────────────────────────────────────────────────────
echo ""
echo -e "${CYAN}════════════════════════════════════════${NC}"
echo -e "${CYAN}  VansRSA 前端打包${NC}"
echo -e "${CYAN}════════════════════════════════════════${NC}"
echo ""

if $BUILD; then
  step "构建前端 ..."
  cd "$WEB_DIR"

  if ! command -v pnpm &>/dev/null; then
    if command -v npm &>/dev/null; then
      warn "pnpm 未安装，尝试使用 npm ..."
      npm install --silent && npm run build
    else
      err "pnpm 和 npm 都未找到，请先安装 Node.js"
      exit 1
    fi
  else
    pnpm install --silent && pnpm build
  fi

  cd "$ROOT"

  if [ ! -d "$DIST_DIR" ]; then
    err "构建失败：$DIST_DIR 目录不存在"
    exit 1
  fi
  FILE_COUNT=$(find "$DIST_DIR" -type f | wc -l)
  DIST_SIZE=$(du -sh "$DIST_DIR" | cut -f1)
  ok "构建完成 → ${FILE_COUNT} 个文件, ${DIST_SIZE}"
else
  if [ ! -d "$DIST_DIR" ]; then
    err "dist 目录不存在: $DIST_DIR（请先构建或去掉 --no-build）"
    exit 1
  fi
  warn "跳过构建（使用已有 dist/）"
fi

# ──────────────────────────────────────────────────────────
# 2. 打包 zip
# ──────────────────────────────────────────────────────────
step "打包 zip ..."
mkdir -p "$OUTPUT_DIR"
OUTPUT_PATH="$OUTPUT_DIR/$OUTPUT_NAME"
rm -f "$OUTPUT_PATH"

cd "$WEB_DIR"
zip -r "$OUTPUT_PATH" dist/ -x "dist/*.gz"
cd "$ROOT"

ZIP_SIZE=$(du -sh "$OUTPUT_PATH" | cut -f1)
ok "打包完成 → $OUTPUT_PATH ($ZIP_SIZE)"

# ──────────────────────────────────────────────────────────
# 3. 完成
# ──────────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}════════════════════════════════════════${NC}"
echo -e "  产物: ${CYAN}${OUTPUT_PATH}${NC}"
echo -e "  大小: ${GREEN}${ZIP_SIZE}${NC}"
echo ""
echo -e "  上传方式:"
echo -e "    管理后台 → 前端热更新 → 选择此 zip 上传"
echo -e "    或 POST ${CYAN}/api/v1/deploy/update-frontend${NC}"
echo -e "${GREEN}════════════════════════════════════════${NC}"
echo ""
