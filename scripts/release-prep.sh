#!/usr/bin/env bash
# ============================================================
# 发版前交互式配置脚本（支持非交互模式）
# 用法:
#   bash scripts/release-prep.sh               # 交互模式，逐项询问
#   bash scripts/release-prep.sh --yes          # 非交互：打印当前值后退出（查看模式）
#   bash scripts/release-prep.sh --yes --set VERSION=1.2.0  # 非交互：直接设置值
#   bash scripts/release-prep.sh --yes --set VERSION=1.2.0 --set DEBUG=False
#   bash scripts/release-prep.sh --dry-run      # 预览模式，不实际修改
#
# 兼容 GNU/Linux 和 macOS/BSD（无 grep -P 依赖）。
# 所有 sed 替换使用 | 分隔符，避免值中含 / 时转义失败。
# ============================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_DIR"

# ── 参数解析 ──────────────────────────────────────────
MODE_INTERACTIVE=true
DRY_RUN=false
declare -A SET_VALUES  # --set KEY=VALUE

while [[ $# -gt 0 ]]; do
    case "$1" in
        --yes|-y)
            MODE_INTERACTIVE=false
            shift
            ;;
        --dry-run|-n)
            DRY_RUN=true
            shift
            ;;
        --set)
            KEY="${2%%=*}"
            VALUE="${2#*=}"
            SET_VALUES["$KEY"]="$VALUE"
            shift 2
            ;;
        *)
            echo "未知参数: $1"
            echo "用法: bash scripts/release-prep.sh [--yes] [--dry-run] [--set KEY=VALUE]..."
            exit 1
            ;;
    esac
done

# ── 颜色 ──────────────────────────────────────────────
if [[ -t 1 ]]; then
    RED='\033[0;31m'
    GREEN='\033[0;32m'
    YELLOW='\033[1;33m'
    CYAN='\033[0;36m'
    BOLD='\033[1m'
    NC='\033[0m'
else
    RED=''; GREEN=''; YELLOW=''; CYAN=''; BOLD=''; NC=''
fi

# ── 辅助函数 ──────────────────────────────────────────

# 安全提取值：从文件中匹配 pattern，返回 group 1
# 用法: extract_val <file> <sed_pattern>
#   例: extract_val pyproject.toml 's/^ *version.*=.*"\([^"]*\)".*/\1/p'
extract_val() {
    local file="$1" pattern="$2"
    if [[ ! -f "$file" ]]; then
        echo "___FILE_NOT_FOUND___"
        return
    fi
    sed -n "$pattern" "$file" | head -1
}

# sed 安全转义：将字符串中的 | & \ 转义，用于 sed 替换右侧
# 注意：左侧（搜索模式）需要额外处理正则元字符
sed_escape_rhs() {
    printf '%s' "$1" | sed 's/[|&\\]/\\&/g'
}

# sed 安全转义：将字符串转义为可用于 sed 搜索模式（右侧不需要）
sed_escape_lhs() {
    printf '%s' "$1" | sed 's/[.[\*^$+?{|()\\]/\\&/g'
}

# 安全替换：对单个文件执行一次 sed 替换，用 | 作为分隔符
# 用法: safe_sed <file> <search_str> <replace_str> <label>
safe_sed() {
    local file="$1" search="$2" replace="$3" label="$4"
    if [ "$DRY_RUN" = true ]; then
        echo -e "  ${YELLOW}[DRY-RUN]${NC} ${label}: ${search} → ${replace}"
        return 0
    fi
    local escaped_lhs escaped_rhs
    escaped_lhs=$(sed_escape_lhs "$search")
    escaped_rhs=$(sed_escape_rhs "$replace")
    if sed -i "s|${escaped_lhs}|${escaped_rhs}|" "$file" 2>/dev/null; then
        echo "  ✓ ${label}"
        return 0
    else
        echo -e "  ${RED}✗${NC} ${label} — 替换失败"
        return 1
    fi
}

# ── 提取所有当前值 ────────────────────────────────────
# 所有提取均使用可移植 sed（无 grep -P 依赖）

check_file() {
    if [[ ! -f "$1" ]]; then
        echo -e "${RED}错误: 文件 $1 不存在${NC}" >&2
        exit 1
    fi
}

check_file pyproject.toml
check_file app/settings/config.py
check_file web/package.json

CUR_VERSION=$(extract_val pyproject.toml 's/^[[:space:]]*version[[:space:]]*=[[:space:]]*"\([^"]*\)".*/\1/p')
CUR_TITLE=$(extract_val app/settings/config.py 's/.*APP_TITLE:[[:space:]]*str[[:space:]]*=[[:space:]]*"\([^"]*\)".*/\1/p')
CUR_PROJ_NAME=$(extract_val app/settings/config.py 's/.*PROJECT_NAME:[[:space:]]*str[[:space:]]*=[[:space:]]*"\([^"]*\)".*/\1/p')
CUR_DESC=$(extract_val app/settings/config.py 's/.*APP_DESCRIPTION:[[:space:]]*str[[:space:]]*=[[:space:]]*"\([^"]*\)".*/\1/p')
CUR_PUBLIC_URL=$(extract_val app/settings/config.py 's/.*PUBLIC_BASE_URL:[[:space:]]*str[[:space:]]*=[[:space:]]*"\([^"]*\)".*/\1/p')
CUR_DEBUG=$(extract_val app/settings/config.py 's/.*DEBUG:[[:space:]]*bool[[:space:]]*=[[:space:]]*\(True\|False\).*/\1/p')
CUR_FE_NAME=$(extract_val web/package.json 's/.*"name":[[:space:]]*"\([^"]*\)".*/\1/p')
CUR_FE_VERSION=$(extract_val web/package.json 's/.*"version":[[:space:]]*"\([^"]*\)".*/\1/p')

# web/.env 可选
CUR_VITE_TITLE=""
if [[ -f web/.env ]]; then
    CUR_VITE_TITLE=$(extract_val web/.env "s/.*VITE_TITLE[[:space:]]*=[[:space:]]*'\([^']*\)'.*/\1/p")
fi

# ── 确定新值 ──────────────────────────────────────────

if [ "$MODE_INTERACTIVE" = true ]; then
    # ── 交互模式 ──────────────────────────────────────

    echo ""
    echo -e "${BOLD}${CYAN}════════════════════════════════════════════════════════${NC}"
    echo -e "${BOLD}${CYAN}  发版前配置检查与修改${NC}"
    echo -e "${BOLD}${CYAN}════════════════════════════════════════════════════════${NC}"
    echo ""
    echo -e "${YELLOW}按 Enter 保留当前值，输入新值覆盖。Ctrl+C 随时退出。${NC}"
    echo ""

    # 1. 版本号
    echo -e "${BOLD}──────────────────────────────────────────────────────${NC}"
    echo -e "${BOLD}1. 版本号${NC}"
    echo -e "  当前: ${YELLOW}${CUR_VERSION}${NC}"
    echo -e "  影响: pyproject.toml / app/settings/config.py / web/package.json"
    read -r -p "  新版本号: " NEW_VERSION
    NEW_VERSION="${NEW_VERSION:-$CUR_VERSION}"

    # 2. DEBUG
    echo ""
    echo -e "${BOLD}──────────────────────────────────────────────────────${NC}"
    echo -e "${BOLD}2. DEBUG 模式${NC}"
    echo -e "  当前: ${YELLOW}${CUR_DEBUG}${NC}  (影响: app/settings/config.py)"
    read -r -p "  [True/False]: " NEW_DEBUG
    NEW_DEBUG="${NEW_DEBUG:-$CUR_DEBUG}"

    # 3. APP_TITLE
    echo ""
    echo -e "${BOLD}──────────────────────────────────────────────────────${NC}"
    echo -e "${BOLD}3. 应用标题 (APP_TITLE)${NC}"
    echo -e "  当前: ${YELLOW}${CUR_TITLE}${NC}  (影响: app/settings/config.py)"
    read -r -p "  新标题: " NEW_TITLE
    NEW_TITLE="${NEW_TITLE:-$CUR_TITLE}"

    # 4. PROJECT_NAME
    echo ""
    echo -e "${BOLD}4. 项目名 (PROJECT_NAME)${NC}"
    echo -e "  当前: ${YELLOW}${CUR_PROJ_NAME}${NC}  (影响: app/settings/config.py)"
    read -r -p "  新项目名: " NEW_PROJ_NAME
    NEW_PROJ_NAME="${NEW_PROJ_NAME:-$CUR_PROJ_NAME}"

    # 5. APP_DESCRIPTION
    echo ""
    echo -e "${BOLD}──────────────────────────────────────────────────────${NC}"
    echo -e "${BOLD}5. 应用描述 (APP_DESCRIPTION)${NC}"
    echo -e "  当前: ${YELLOW}${CUR_DESC}${NC}  (影响: app/settings/config.py)"
    read -r -p "  新描述: " NEW_DESC
    NEW_DESC="${NEW_DESC:-$CUR_DESC}"

    # 6. PUBLIC_BASE_URL
    echo ""
    echo -e "${BOLD}──────────────────────────────────────────────────────${NC}"
    echo -e "${BOLD}6. 公网访问地址 (PUBLIC_BASE_URL)${NC}"
    echo -e "  当前: ${YELLOW}${CUR_PUBLIC_URL}${NC}  (影响: app/settings/config.py)"
    echo -e "  ${YELLOW}⚠  用于短链接生成，如留空则写空字符串${NC}"
    read -r -p "  新地址: " NEW_PUBLIC_URL
    NEW_PUBLIC_URL="${NEW_PUBLIC_URL:-$CUR_PUBLIC_URL}"

    # 7. 前端包名
    echo ""
    echo -e "${BOLD}──────────────────────────────────────────────────────${NC}"
    echo -e "${BOLD}7. 前端包名 (web/package.json name)${NC}"
    echo -e "  当前: ${YELLOW}${CUR_FE_NAME}${NC}"
    read -r -p "  新包名: " NEW_FE_NAME
    NEW_FE_NAME="${NEW_FE_NAME:-$CUR_FE_NAME}"

    # 8. 前端标题
    echo ""
    echo -e "${BOLD}──────────────────────────────────────────────────────${NC}"
    echo -e "${BOLD}8. 前端页面标题 (VITE_TITLE)${NC}"
    echo -e "  当前: ${YELLOW}${CUR_VITE_TITLE}${NC}${CUR_VITE_TITLE:+  (影响: web/.env)}"
    [[ -z "$CUR_VITE_TITLE" ]] && echo -e "  ${YELLOW}⚠  web/.env 不存在或未设 VITE_TITLE${NC}"
    read -r -p "  新标题: " NEW_VITE_TITLE
    NEW_VITE_TITLE="${NEW_VITE_TITLE:-$CUR_VITE_TITLE}"

    # ── 汇总确认 ──────────────────────────────────────
    echo ""
    echo -e "${BOLD}${CYAN}════════════════════════════════════════════════════════${NC}"
    echo -e "${BOLD}${CYAN}  确认更改${NC}"
    echo -e "${BOLD}${CYAN}════════════════════════════════════════════════════════${NC}"
    echo ""
    echo -e "  版本号:          ${YELLOW}${CUR_VERSION}${NC} → ${GREEN}${NEW_VERSION}${NC}"
    echo -e "  DEBUG:           ${YELLOW}${CUR_DEBUG}${NC} → ${GREEN}${NEW_DEBUG}${NC}"
    echo -e "  APP_TITLE:       ${YELLOW}${CUR_TITLE}${NC} → ${GREEN}${NEW_TITLE}${NC}"
    echo -e "  PROJECT_NAME:    ${YELLOW}${CUR_PROJ_NAME}${NC} → ${GREEN}${NEW_PROJ_NAME}${NC}"
    echo -e "  APP_DESCRIPTION: ${YELLOW}${CUR_DESC}${NC} → ${GREEN}${NEW_DESC}${NC}"
    echo -e "  PUBLIC_BASE_URL: ${YELLOW}${CUR_PUBLIC_URL}${NC} → ${GREEN}${NEW_PUBLIC_URL}${NC}"
    echo -e "  前端包名:        ${YELLOW}${CUR_FE_NAME}${NC} → ${GREEN}${NEW_FE_NAME}${NC}"
    echo -e "  前端标题:        ${YELLOW}${CUR_VITE_TITLE}${NC} → ${GREEN}${NEW_VITE_TITLE}${NC}"
    echo ""

    echo -e "${YELLOW}将修改以下文件:${NC}"
    echo "  - pyproject.toml"
    echo "  - app/settings/config.py"
    echo "  - web/package.json"
    [[ -n "$CUR_VITE_TITLE" ]] && echo "  - web/.env"
    echo ""

    read -r -p "$(echo -e "${BOLD}确认执行以上更改? [y/N]: ${NC}")" CONFIRM

    if [[ ! "$CONFIRM" =~ ^[Yy]$ ]]; then
        echo -e "${RED}已取消。${NC}"
        exit 0
    fi

else
    # ── 非交互模式：默认保留当前值，--set 覆盖 ──────

    NEW_VERSION="${SET_VALUES[VERSION]:-$CUR_VERSION}"
    NEW_DEBUG="${SET_VALUES[DEBUG]:-$CUR_DEBUG}"
    NEW_TITLE="${SET_VALUES[APP_TITLE]:-$CUR_TITLE}"
    NEW_PROJ_NAME="${SET_VALUES[PROJECT_NAME]:-$CUR_PROJ_NAME}"
    NEW_DESC="${SET_VALUES[APP_DESCRIPTION]:-$CUR_DESC}"
    NEW_PUBLIC_URL="${SET_VALUES[PUBLIC_BASE_URL]:-$CUR_PUBLIC_URL}"
    NEW_FE_NAME="${SET_VALUES[FE_NAME]:-$CUR_FE_NAME}"
    NEW_VITE_TITLE="${SET_VALUES[VITE_TITLE]:-$CUR_VITE_TITLE}"

    echo ""
    echo -e "${BOLD}${CYAN}════════════════════════════════════════════════════════${NC}"
    echo -e "${BOLD}${CYAN}  发版配置${DRY_RUN:+ [DRY-RUN]}${NC}"
    echo -e "${BOLD}${CYAN}════════════════════════════════════════════════════════${NC}"
    echo ""
    echo -e "  版本号:          ${YELLOW}${CUR_VERSION}${NC} → ${GREEN}${NEW_VERSION}${NC}"
    echo -e "  DEBUG:           ${YELLOW}${CUR_DEBUG}${NC} → ${GREEN}${NEW_DEBUG}${NC}"
    echo -e "  APP_TITLE:       ${YELLOW}${CUR_TITLE}${NC} → ${GREEN}${NEW_TITLE}${NC}"
    echo -e "  PROJECT_NAME:    ${YELLOW}${CUR_PROJ_NAME}${NC} → ${GREEN}${NEW_PROJ_NAME}${NC}"
    echo -e "  APP_DESCRIPTION: ${YELLOW}${CUR_DESC}${NC} → ${GREEN}${NEW_DESC}${NC}"
    echo -e "  PUBLIC_BASE_URL: ${YELLOW}${CUR_PUBLIC_URL}${NC} → ${GREEN}${NEW_PUBLIC_URL}${NC}"
    echo -e "  前端包名:        ${YELLOW}${CUR_FE_NAME}${NC} → ${GREEN}${NEW_FE_NAME}${NC}"
    echo -e "  前端标题:        ${YELLOW}${CUR_VITE_TITLE}${NC} → ${GREEN}${NEW_VITE_TITLE}${NC}"
    echo ""
fi

# ── 备份 ──────────────────────────────────────────────
if [ "$DRY_RUN" = false ]; then
    BACKUP_DIR="/tmp/release-prep-backup-$(date +%Y%m%d_%H%M%S)"
    mkdir -p "$BACKUP_DIR"
    cp pyproject.toml "$BACKUP_DIR/"
    cp app/settings/config.py "$BACKUP_DIR/"
    cp web/package.json "$BACKUP_DIR/"
    [[ -f web/.env ]] && cp web/.env "$BACKUP_DIR/"
fi

# ── 执行修改 ──────────────────────────────────────────
echo ""
echo -e "${BOLD}正在应用更改...${NC}"

CHANGED=0

# pyproject.toml — version
if [ "$NEW_VERSION" != "$CUR_VERSION" ]; then
    safe_sed pyproject.toml \
        "version = \"${CUR_VERSION}\"" \
        "version = \"${NEW_VERSION}\"" \
        "pyproject.toml version" && ((CHANGED++))
fi

# app/settings/config.py — VERSION
if [ "$NEW_VERSION" != "$CUR_VERSION" ]; then
    safe_sed app/settings/config.py \
        "VERSION: str = \"${CUR_VERSION}\"" \
        "VERSION: str = \"${NEW_VERSION}\"" \
        "config.py VERSION" && ((CHANGED++))
fi

# app/settings/config.py — APP_TITLE
if [ "$NEW_TITLE" != "$CUR_TITLE" ]; then
    safe_sed app/settings/config.py \
        "APP_TITLE: str = \"${CUR_TITLE}\"" \
        "APP_TITLE: str = \"${NEW_TITLE}\"" \
        "config.py APP_TITLE" && ((CHANGED++))
fi

# app/settings/config.py — PROJECT_NAME
if [ "$NEW_PROJ_NAME" != "$CUR_PROJ_NAME" ]; then
    safe_sed app/settings/config.py \
        "PROJECT_NAME: str = \"${CUR_PROJ_NAME}\"" \
        "PROJECT_NAME: str = \"${NEW_PROJ_NAME}\"" \
        "config.py PROJECT_NAME" && ((CHANGED++))
fi

# app/settings/config.py — APP_DESCRIPTION
if [ "$NEW_DESC" != "$CUR_DESC" ]; then
    safe_sed app/settings/config.py \
        "APP_DESCRIPTION: str = \"${CUR_DESC}\"" \
        "APP_DESCRIPTION: str = \"${NEW_DESC}\"" \
        "config.py APP_DESCRIPTION" && ((CHANGED++))
fi

# app/settings/config.py — PUBLIC_BASE_URL
if [ "$NEW_PUBLIC_URL" != "$CUR_PUBLIC_URL" ]; then
    safe_sed app/settings/config.py \
        "PUBLIC_BASE_URL: str = \"${CUR_PUBLIC_URL}\"" \
        "PUBLIC_BASE_URL: str = \"${NEW_PUBLIC_URL}\"" \
        "config.py PUBLIC_BASE_URL" && ((CHANGED++))
fi

# app/settings/config.py — DEBUG
if [ "$NEW_DEBUG" != "$CUR_DEBUG" ]; then
    safe_sed app/settings/config.py \
        "DEBUG: bool = ${CUR_DEBUG}" \
        "DEBUG: bool = ${NEW_DEBUG}" \
        "config.py DEBUG" && ((CHANGED++))
fi

# web/package.json — name
if [ "$NEW_FE_NAME" != "$CUR_FE_NAME" ]; then
    safe_sed web/package.json \
        "\"name\": \"${CUR_FE_NAME}\"" \
        "\"name\": \"${NEW_FE_NAME}\"" \
        "package.json name" && ((CHANGED++))
fi

# web/package.json — version
if [ "$NEW_VERSION" != "$CUR_FE_VERSION" ]; then
    safe_sed web/package.json \
        "\"version\": \"${CUR_FE_VERSION}\"" \
        "\"version\": \"${NEW_VERSION}\"" \
        "package.json version" && ((CHANGED++))
fi

# web/.env — VITE_TITLE
if [[ -f web/.env ]] && [ "$NEW_VITE_TITLE" != "$CUR_VITE_TITLE" ]; then
    safe_sed web/.env \
        "VITE_TITLE = '${CUR_VITE_TITLE}'" \
        "VITE_TITLE = '${NEW_VITE_TITLE}'" \
        ".env VITE_TITLE" && ((CHANGED++))
fi

# ── 完成 ──────────────────────────────────────────────
echo ""
echo -e "${BOLD}${GREEN}════════════════════════════════════════════════════════${NC}"
if [ "$DRY_RUN" = true ]; then
    echo -e "${BOLD}${YELLOW}  🔍 DRY-RUN — 未修改任何文件${NC}"
else
    echo -e "${BOLD}${GREEN}  ✅ 已修改 ${CHANGED} 处${NC}"
fi
echo -e "${BOLD}${GREEN}════════════════════════════════════════════════════════${NC}"
echo ""

if [ "$DRY_RUN" = false ] && [ "$CHANGED" -gt 0 ]; then
    echo -e "  备份目录: ${CYAN}${BACKUP_DIR}${NC}"
    echo ""
    echo -e "  ${YELLOW}建议执行:${NC}"
    echo "    git diff                    # 查看改动"
    echo "    git add -A && git commit    # 提交"
    echo "    git tag v${NEW_VERSION}      # 打标签"
    echo "    bash build-docker.sh ${NEW_VERSION}  # 构建镜像"
    echo ""
    echo -e "  ${YELLOW}如需回滚:${NC}"
    echo "    cp ${BACKUP_DIR}/* ."
fi
echo ""
