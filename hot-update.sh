#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────
# VansRSA 前端热更新 — 一键构建 + 打包 + 上传到远程服务器
#
# 用法:
#   ./hot-update.sh                    # 构建 + 上传
#   ./hot-update.sh --no-build         # 跳过构建，上传已有 dist/
#   ./hot-update.sh --build-only       # 仅构建 + 打包，不上传
#   ./hot-update.sh -h                 # 帮助
#
# 环境变量（可覆盖默认值）:
#   REMOTE_URL       服务器地址   (默认 http://192.168.0.153:1110)
#   REMOTE_USER      登录用户名   (默认 Vance)
#   REMOTE_PASS      登录密码
#   WEB_DIR          前端目录     (默认 ./web)
# ──────────────────────────────────────────────────────────

set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

# ── 默认配置 ──
REMOTE_URL="${REMOTE_URL:-http://192.168.0.153:1110}"
REMOTE_USER="${REMOTE_USER:-Vance}"
REMOTE_PASS="${REMOTE_PASS:-}"
WEB_DIR="${WEB_DIR:-$ROOT/web}"
DIST_DIR="$WEB_DIR/dist"
OUTPUT_DIR="$ROOT/dist_package"

BUILD=true
UPLOAD=true

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
  echo "  --no-build          跳过构建，上传已有 dist/"
  echo "  --build-only        仅构建 + 打包，不上传"
  echo "  -p, --password PW   指定密码（不指定则从环境变量 REMOTE_PASS 读取）"
  echo "  -h, --help          显示帮助"
  echo ""
  echo "环境变量:"
  echo "  REMOTE_URL    服务器地址 (默认 $REMOTE_URL)"
  echo "  REMOTE_USER   登录用户名 (默认 $REMOTE_USER)"
  echo "  REMOTE_PASS   登录密码"
  echo ""
  echo "示例:"
  echo "  $0                              # 构建 + 打包 + 上传 (从环境变量读密码)"
  echo "  $0 -p 'mypassword'              # 命令行指定密码"
  echo "  $0 --no-build -p 'xxx'          # 跳过构建，直接上传已有 dist/"
  echo "  $0 --build-only                 # 仅构建，生成 zip 在 dist_package/"
  exit 0
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --no-build)   BUILD=false; shift ;;
    --build-only) UPLOAD=false; shift ;;
    -p|--password) REMOTE_PASS="$2"; shift 2 ;;
    -h|--help)    usage ;;
    *)            err "未知选项: $1"; usage ;;
  esac
done

TIMESTAMP=$(date +%Y%m%d-%H%M%S)
ZIP_NAME="hotfix-${TIMESTAMP}.zip"
ZIP_PATH="$OUTPUT_DIR/$ZIP_NAME"

echo ""
echo -e "${CYAN}════════════════════════════════════════${NC}"
echo -e "${CYAN}  VansRSA 前端热更新${NC}"
echo -e "${CYAN}════════════════════════════════════════${NC}"
echo "  服务器:     ${GREEN}${REMOTE_URL}${NC}"
echo "  用户:       ${GREEN}${REMOTE_USER}${NC}"
echo "  构建:       $( $BUILD && echo -e "${GREEN}是${NC}" || echo -e "${YELLOW}跳过${NC}" )"
echo "  上传:       $( $UPLOAD && echo -e "${GREEN}是${NC}" || echo -e "${YELLOW}跳过${NC}" )"
echo ""

# ──────────────────────────────────────────────────────────
# 1. 构建前端
# ──────────────────────────────────────────────────────────
if $BUILD; then
  step "构建前端 ..."
  cd "$WEB_DIR"

  if ! command -v pnpm &>/dev/null; then
    if command -v npm &>/dev/null; then
      warn "pnpm 未安装，使用 npm ..."
      npm install --silent && npm run build
    else
      err "pnpm 和 npm 都未安装"
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
    err "dist 目录不存在: $DIST_DIR"
    exit 1
  fi
  warn "跳过构建（使用已有 dist/）"
fi

# ──────────────────────────────────────────────────────────
# 2. 打包 zip
# ──────────────────────────────────────────────────────────
step "打包 zip ..."
mkdir -p "$OUTPUT_DIR"
rm -f "$ZIP_PATH"

cd "$WEB_DIR"
zip -r "$ZIP_PATH" dist/ -x "dist/*.gz" >/dev/null
cd "$ROOT"

ZIP_SIZE=$(du -sh "$ZIP_PATH" | cut -f1)
ok "打包完成 → $ZIP_PATH ($ZIP_SIZE)"

if ! $UPLOAD; then
  echo ""
  echo -e "${GREEN}════════════════════════════════════════${NC}"
  echo -e "  产物: ${CYAN}${ZIP_PATH}${NC}"
  echo -e "  大小: ${GREEN}${ZIP_SIZE}${NC}"
  echo -e "${GREEN}════════════════════════════════════════${NC}"
  echo ""
  exit 0
fi

# ──────────────────────────────────────────────────────────
# 3. 上传到远程服务器
# ──────────────────────────────────────────────────────────
step "连接服务器 $REMOTE_URL ..."

# 检查密码
if [ -z "$REMOTE_PASS" ]; then
  err "未设置密码。请通过 -p 参数或 REMOTE_PASS 环境变量提供"
  echo ""
  echo "  用法:"
  echo "    $0 -p 'your_password'"
  echo "    export REMOTE_PASS='your_password' && $0"
  exit 1
fi

# 3a. 登录获取 Token
step "获取 Token ..."
TOKEN=$(curl -s --noproxy '*' --connect-timeout 10 \
  -X POST "${REMOTE_URL}/api/v1/base/access_token" \
  -H "Content-Type: application/json" \
  -d "{\"username\":\"${REMOTE_USER}\",\"password\":\"${REMOTE_PASS}\"}" \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['data']['access_token'])" 2>/dev/null) || true

if [ -z "$TOKEN" ] || [ "$TOKEN" = "null" ]; then
  err "登录失败：无法获取 Token"
  echo ""
  echo "  请检查:"
  echo "    - 服务器地址是否正确: $REMOTE_URL"
  echo "    - 用户名/密码是否正确"
  echo "    - 服务器是否在运行"
  exit 1
fi
ok "Token 获取成功"

# 3b. 上传 zip
step "上传前端产物 (${ZIP_SIZE}) ..."
UPLOAD_RESULT=$(curl -s --noproxy '*' --connect-timeout 10 \
  -X POST "${REMOTE_URL}/api/v1/deploy/update-frontend" \
  -H "token: ${TOKEN}" \
  -F "file=@${ZIP_PATH}" 2>&1) || true

if echo "$UPLOAD_RESULT" | python3 -c "import sys,json; d=json.load(sys.stdin); exit(0 if d.get('code')==200 else 1)" 2>/dev/null; then
  ok "上传成功 → Ctrl+F5 强制刷新浏览器即可看到更新"
else
  err "上传失败"
  echo "  响应: $UPLOAD_RESULT"
  echo ""
  echo "  常见原因:"
  echo "    - Token 过期（重新运行即可）"
  echo "    - 服务器磁盘空间不足"
  echo "    - 网络不通（检查 --noproxy '*' 是否生效）"
  exit 1
fi

# ──────────────────────────────────────────────────────────
# 4. 完成
# ──────────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}════════════════════════════════════════${NC}"
echo -e "  状态: ${GREEN}完成${NC}"
echo -e "  产物: ${CYAN}${ZIP_PATH}${NC}"
echo -e "  服务器: ${CYAN}${REMOTE_URL}${NC}"
echo -e "  ⚡ Ctrl+F5 强制刷新浏览器${NC}"
echo -e "${GREEN}════════════════════════════════════════${NC}"
echo ""
