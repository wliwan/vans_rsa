#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────
# VansRSA 后端热更新 — 打包后端代码 + 上传到远程服务器
#
# 用法:
#   ./hot-update-be.sh                    # 打包 app/ + 上传
#   ./hot-update-be.sh --build-only       # 仅打包，不上传
#   ./hot-update-be.sh -p 'password'      # 指定密码
#
# 注意：上传后容器会自动重启（约 5-15 秒恢复）
# ──────────────────────────────────────────────────────────

set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

# ── 默认配置 ──
REMOTE_URL="${REMOTE_URL:-http://192.168.0.153:1110}"
REMOTE_USER="${REMOTE_USER:-Vance}"
REMOTE_PASS="${REMOTE_PASS:-}"
APP_DIR="$ROOT/app"
OUTPUT_DIR="$ROOT/dist_package"

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
  echo "  --build-only        仅打包，不上传"
  echo "  -p, --password PW   指定密码"
  echo "  -h, --help          显示帮助"
  echo ""
  echo "环境变量: REMOTE_URL / REMOTE_USER / REMOTE_PASS"
  exit 0
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --build-only) UPLOAD=false; shift ;;
    -p|--password) REMOTE_PASS="$2"; shift 2 ;;
    -h|--help)    usage ;;
    *)            err "未知选项: $1"; usage ;;
  esac
done

TIMESTAMP=$(date +%Y%m%d-%H%M%S)
ZIP_NAME="backend-${TIMESTAMP}.zip"
ZIP_PATH="$OUTPUT_DIR/$ZIP_NAME"
ZIP_INCLUDE=(
  "app/"
  "run.py"
  "requirements.txt"
  "pyproject.toml"
)

echo ""
echo -e "${CYAN}════════════════════════════════════════${NC}"
echo -e "${CYAN}  VansRSA 后端热更新${NC}"
echo -e "${CYAN}════════════════════════════════════════${NC}"
echo "  服务器:     ${GREEN}${REMOTE_URL}${NC}"
echo "  上传:       $( $UPLOAD && echo -e "${GREEN}是${NC}" || echo -e "${YELLOW}跳过${NC}" )"
echo ""

# ──────────────────────────────────────────────────────────
# 1. 打包后端代码
# ──────────────────────────────────────────────────────────
step "打包后端代码 ..."
mkdir -p "$OUTPUT_DIR"
rm -f "$ZIP_PATH"

# 只打包存在的文件/目录
ZIP_ARGS=()
for item in "${ZIP_INCLUDE[@]}"; do
  if [ -e "$ROOT/$item" ]; then
    ZIP_ARGS+=("$item")
  else
    warn "跳过不存在的: $item"
  fi
done

cd "$ROOT"
zip -r "$ZIP_PATH" "${ZIP_ARGS[@]}" -x "app/__pycache__/*" "app/**/__pycache__/*" "*.pyc" "app/logs/*" >/dev/null
cd "$ROOT"

ZIP_SIZE=$(du -sh "$ZIP_PATH" | cut -f1)
FILE_COUNT=$(unzip -l "$ZIP_PATH" | tail -1 | awk '{print $2}')
ok "打包完成 → ${FILE_COUNT} 个条目, ${ZIP_SIZE}"

if ! $UPLOAD; then
  echo ""
  echo -e "${GREEN}════════════════════════════════════════${NC}"
  echo -e "  产物: ${CYAN}${ZIP_PATH}${NC}"
  echo -e "${GREEN}════════════════════════════════════════${NC}"
  echo ""
  exit 0
fi

# ──────────────────────────────────────────────────────────
# 2. 上传
# ──────────────────────────────────────────────────────────
if [ -z "$REMOTE_PASS" ]; then
  err "未设置密码。请通过 -p 参数或 REMOTE_PASS 环境变量提供"
  exit 1
fi

step "获取 Token ..."
TOKEN=$(curl -s --noproxy '*' --connect-timeout 10 \
  -X POST "${REMOTE_URL}/api/v1/base/access_token" \
  -H "Content-Type: application/json" \
  -d "{\"username\":\"${REMOTE_USER}\",\"password\":\"${REMOTE_PASS}\"}" \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['data']['access_token'])" 2>/dev/null) || true

if [ -z "$TOKEN" ] || [ "$TOKEN" = "null" ]; then
  err "登录失败"
  exit 1
fi
ok "Token 获取成功"

step "上传后端代码 (${ZIP_SIZE})，上传后容器将自动重启 ..."
UPLOAD_RESULT=$(curl -s --noproxy '*' --connect-timeout 60 \
  -X POST "${REMOTE_URL}/api/v1/deploy/update-backend" \
  -H "token: ${TOKEN}" \
  -F "file=@${ZIP_PATH}" 2>&1) || true

if echo "$UPLOAD_RESULT" | python3 -c "import sys,json; d=json.load(sys.stdin); exit(0 if d.get('code')==200 else 1)" 2>/dev/null; then
  ok "上传成功，后端正在重启..."

  # 等待服务恢复
  step "等待服务恢复 ..."
  for i in $(seq 1 30); do
    if curl -s --noproxy '*' --connect-timeout 3 "${REMOTE_URL}/api/v1/base/access_token" >/dev/null 2>&1; then
      ok "服务已恢复（耗时约 ${i} 秒）"
      break
    fi
    sleep 1
  done
else
  err "上传失败"
  echo "  响应: $UPLOAD_RESULT"
  echo ""
  echo "  注意: 如果是因为语法错误被拒，本地运行 python -m compileall app/ 排查"
  exit 1
fi

echo ""
echo -e "${GREEN}════════════════════════════════════════${NC}"
echo -e "  状态: ${GREEN}完成${NC}"
echo -e "  旧代码备份: ${CYAN}/opt/VansRSA/app_backup/${NC}"
echo -e "${GREEN}════════════════════════════════════════${NC}"
echo ""
