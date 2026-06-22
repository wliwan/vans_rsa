#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────
# VansRSA 前端热更新脚本（仅更新 Docker 容器中的编译产物）
#
# 适用场景：后端未变，只改了前端代码，不想重建整个镜像。
#
# 用法:
#   ./update-frontend.sh                  # 默认容器名 VansRSA
#   ./update-frontend.sh my-container     # 指定容器名
#   ./update-frontend.sh --build-only     # 仅本地构建，不推送容器
#   ./update-frontend.sh --no-build       # 跳过构建，直接推送已有 dist
#   ./update-frontend.sh -c my-container  # -c 指定容器名
#
# 环境变量:
#   CONTAINER   - 容器名（默认 VansRSA）
#   WEB_DIR     - 前端目录（默认 ./web）
#   DIST_DIR    - 编译产物目录（默认 web/dist）
# ──────────────────────────────────────────────────────────

set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

# ── 默认值 ──
CONTAINER="${CONTAINER:-VansRSA}"
WEB_DIR="${WEB_DIR:-$ROOT/web}"
DIST_DIR="${DIST_DIR:-$WEB_DIR/dist}"
CONTAINER_DIST="/opt/VansRSA/web/dist"
BUILD=true
PUSH=true

# ── 颜色 ──
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'
step()  { echo -e "${CYAN}➜ $*${NC}"; }
ok()    { echo -e "${GREEN}✔ $*${NC}"; }
warn()  { echo -e "${YELLOW}⚠ $*${NC}"; }
err()   { echo -e "${RED}✘ $*${NC}"; }

# ── 帮助 ──
usage() {
  echo "用法: $0 [选项] [容器名]"
  echo ""
  echo "选项:"
  echo "  -c, --container NAME   指定 Docker 容器名（默认: VansRSA）"
  echo "  --build-only           仅本地构建，不推送到容器"
  echo "  --no-build             跳过构建，直接推送已有 dist/"
  echo "  -h, --help             显示帮助"
  echo ""
  echo "环境变量:"
  echo "  CONTAINER   容器名（默认 VansRSA）"
  echo "  WEB_DIR     前端目录（默认 ./web）"
  echo ""
  echo "示例:"
  echo "  $0                          # 构建 + 推送到 VansRSA"
  echo "  $0 my-vansrsa               # 推送到指定容器"
  echo "  $0 -c prod --no-build       # 跳过构建，直接推送"
  echo "  $0 --build-only             # 仅构建"
  exit 0
}

# ── 解析参数 ──
while [[ $# -gt 0 ]]; do
  case "$1" in
    -c|--container)
      CONTAINER="$2"; shift 2 ;;
    --build-only)
      PUSH=false; shift ;;
    --no-build)
      BUILD=false; shift ;;
    -h|--help)
      usage ;;
    -*)
      err "未知选项: $1"; usage ;;
    *)
      CONTAINER="$1"; shift ;;
  esac
done

# ──────────────────────────────────────────────────────────
# 1. 检查前置条件
# ──────────────────────────────────────────────────────────
echo ""
echo -e "${CYAN}════════════════════════════════════════${NC}"
echo -e "${CYAN}  VansRSA 前端热更新${NC}"
echo -e "${CYAN}════════════════════════════════════════${NC}"
echo "  容器名:     ${GREEN}${CONTAINER}${NC}"
echo "  前端目录:   ${GREEN}${WEB_DIR}${NC}"
echo "  编译产物:   ${GREEN}${DIST_DIR}${NC}"
echo "  容器内路径: ${GREEN}${CONTAINER_DIST}${NC}"
echo ""

if $PUSH; then
  if ! docker ps --format '{{.Names}}' 2>/dev/null | grep -qx "$CONTAINER"; then
    err "容器 '$CONTAINER' 未运行"
    echo ""
    echo "  运行中的容器列表:"
    docker ps --format '  {{.Names}}  ({{.Status}})'
    echo ""
    echo "  请先启动容器或指定正确的容器名: $0 -c <容器名>"
    exit 1
  fi
  ok "容器 '$CONTAINER' 运行中"
fi

# ──────────────────────────────────────────────────────────
# 2. 构建前端
# ──────────────────────────────────────────────────────────
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

  # 统计文件数和大小
  FILE_COUNT=$(find "$DIST_DIR" -type f | wc -l)
  DIST_SIZE=$(du -sh "$DIST_DIR" | cut -f1)
  ok "构建完成 → ${FILE_COUNT} 个文件, ${DIST_SIZE}"
else
  if [ ! -d "$DIST_DIR" ]; then
    err "dist 目录不存在: $DIST_DIR（请先运行构建，或去掉 --no-build）"
    exit 1
  fi
  warn "跳过构建（使用已有 dist/）"
fi

# ──────────────────────────────────────────────────────────
# 3. 推送到容器
# ──────────────────────────────────────────────────────────
if $PUSH; then
  step "推送前端文件到容器 ..."

  # 确保容器内目标目录存在
  docker exec "$CONTAINER" mkdir -p "$CONTAINER_DIST" 2>/dev/null || true

  # 复制编译产物到容器（用 . 而不是 * 避免 shell glob 问题）
  docker cp "$DIST_DIR/." "$CONTAINER:$CONTAINER_DIST/"

  # 验证：检查容器内的 index.html
  if docker exec "$CONTAINER" test -f "$CONTAINER_DIST/index.html" 2>/dev/null; then
    CONTAINER_SIZE=$(docker exec "$CONTAINER" du -sh "$CONTAINER_DIST" 2>/dev/null | cut -f1)
    ok "推送完成 → 容器内 $CONTAINER_SIZE"
  else
    err "推送后验证失败：容器内 $CONTAINER_DIST/index.html 不存在"
    exit 1
  fi
fi

# ──────────────────────────────────────────────────────────
# 4. 完成
# ──────────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}════════════════════════════════════════${NC}"
echo -e "  状态: ${GREEN}完成${NC}"
if $PUSH; then
  echo -e "  容器: ${CYAN}${CONTAINER}${NC}"
  echo -e "  访问: ${CYAN}http://localhost:1110${NC}（默认端口）"
fi
echo -e "${GREEN}════════════════════════════════════════${NC}"
echo ""
