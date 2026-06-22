#!/usr/bin/env bash
# ============================================================
# VansRSA (Vance Road Scanner Assistant) 主机打包脚本
#
# 功能:
#   1. 自动提取当前版本号
#   2. 自动迭代次版本号 (patch +1)
#   3. 更新所有配置文件的版本号
#   4. 构建前端产物
#   5. 打包为 zip 分发
#   6. 自动 git 提交版本变更并打 tag
#
# 用法:
#   bash vansrsa-package.sh              # 自动迭代 patch 版本
#   bash vansrsa-package.sh --minor      # 迭代 minor 版本 (0.1.0 → 0.2.0)
#   bash vansrsa-package.sh --major      # 迭代 major 版本 (0.1.0 → 1.0.0)
#   bash vansrsa-package.sh --set 1.2.0  # 指定版本号
#   bash vansrsa-package.sh --dry-run    # 预览模式，不实际修改/打包
#
# 输出: dist_package/VansRSA_vX.Y.Z_YYYYMMDD_HHMMSS.zip
# ============================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$SCRIPT_DIR"
cd "$PROJECT_DIR"

# ═══════════════════════════════════════════════════════════════
# 配置常量
# ═══════════════════════════════════════════════════════════════
PROJECT_NAME="VansRSA"
PROJECT_DESC="Vance Road Scanner Assistant"
OUTPUT_DIR="${PROJECT_DIR}/dist_package"

# 需要更新版本号的文件及匹配模式
declare -A VERSION_FILES=(
    ["pyproject.toml"]='s/^[[:space:]]*version[[:space:]]*=[[:space:]]*"\([^"]*\)".*/\1/p'
    ["app/settings/config.py"]='s/.*VERSION:[[:space:]]*str[[:space:]]*=[[:space:]]*"\([^"]*\)".*/\1/p'
    ["web/package.json"]='s/.*"version":[[:space:]]*"\([^"]*\)".*/\1/p'
)

# ═══════════════════════════════════════════════════════════════
# 参数解析
# ═══════════════════════════════════════════════════════════════
BUMP_MODE="patch"
SPECIFIED_VERSION=""
DRY_RUN=false

while [[ $# -gt 0 ]]; do
    case "$1" in
        --minor)  BUMP_MODE="minor";  shift ;;
        --major)  BUMP_MODE="major";  shift ;;
        --set)    SPECIFIED_VERSION="$2"; shift 2 ;;
        --dry-run|-n) DRY_RUN=true; shift ;;
        -h|--help)
            echo "用法: bash vansrsa-package.sh [选项]"
            echo ""
            echo "选项:"
            echo "  (无参数)      自动迭代 patch 版本 (0.1.0 → 0.1.1)"
            echo "  --minor       迭代 minor 版本 (0.1.0 → 0.2.0)"
            echo "  --major       迭代 major 版本 (0.1.0 → 1.0.0)"
            echo "  --set X.Y.Z   指定版本号"
            echo "  --dry-run, -n 预览模式，不实际修改文件/打包"
            echo "  -h, --help    显示帮助"
            exit 0
            ;;
        *) echo "未知参数: $1"; exit 1 ;;
    esac
done

# ═══════════════════════════════════════════════════════════════
# 颜色
# ═══════════════════════════════════════════════════════════════
if [[ -t 1 ]]; then
    RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
    CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'
else
    RED=''; GREEN=''; YELLOW=''; CYAN=''; BOLD=''; NC=''
fi

# ═══════════════════════════════════════════════════════════════
# 辅助函数
# ═══════════════════════════════════════════════════════════════

bump_version() {
    # $1=当前版本 "X.Y.Z", $2=mode (patch|minor|major)
    local ver="$1" mode="$2"
    local major minor patch
    IFS='.' read -r major minor patch <<< "$ver"
    case "$mode" in
        major) echo "$((major + 1)).0.0" ;;
        minor) echo "${major}.$((minor + 1)).0" ;;
        patch) echo "${major}.${minor}.$((patch + 1))" ;;
        *)     echo "$ver" ;;
    esac
}

replace_version_in_file() {
    local file="$1" old_ver="$2" new_ver="$3"
    if [ "$DRY_RUN" = true ]; then
        echo -e "  ${YELLOW}[DRY-RUN]${NC} ${file}: ${old_ver} → ${new_ver}"
        return 0
    fi
    # 使用 sed 替换 version = "old" → version = "new"
    if sed -i "s|\"${old_ver}\"|\"${new_ver}\"|g" "$file" 2>/dev/null; then
        echo -e "  ${GREEN}✓${NC} ${file}"
        return 0
    else
        echo -e "  ${RED}✗${NC} ${file} 替换失败"
        return 1
    fi
}

# ═══════════════════════════════════════════════════════════════
# 步骤 1: 提取当前版本
# ═══════════════════════════════════════════════════════════════

echo ""
echo -e "${BOLD}${CYAN}════════════════════════════════════════════════════════${NC}"
echo -e "${BOLD}${CYAN}  ${PROJECT_NAME} 打包脚本${DRY_RUN:+ [DRY-RUN]}${NC}"
echo -e "${BOLD}${CYAN}  ${PROJECT_DESC}${NC}"
echo -e "${BOLD}${CYAN}════════════════════════════════════════════════════════${NC}"
echo ""

CUR_VERSION=""
for file in pyproject.toml app/settings/config.py web/package.json; do
    if [[ ! -f "$file" ]]; then
        echo -e "${RED}错误: $file 不存在${NC}" >&2
        exit 1
    fi
done

# 从 pyproject.toml 读取版本号作为权威源
CUR_VERSION=$(sed -n 's/^[[:space:]]*version[[:space:]]*=[[:space:]]*"\([^"]*\)".*/\1/p' pyproject.toml | head -1)

if [[ -z "$CUR_VERSION" ]]; then
    echo -e "${RED}错误: 无法从 pyproject.toml 提取版本号${NC}" >&2
    exit 1
fi

# 计算新版本
if [[ -n "$SPECIFIED_VERSION" ]]; then
    NEW_VERSION="$SPECIFIED_VERSION"
    echo "  当前版本: ${YELLOW}${CUR_VERSION}${NC}"
    echo "  指定版本: ${GREEN}${NEW_VERSION}${NC}"
else
    NEW_VERSION=$(bump_version "$CUR_VERSION" "$BUMP_MODE")
    echo "  当前版本: ${YELLOW}${CUR_VERSION}${NC}"
    echo "  迭代模式: ${CYAN}${BUMP_MODE}${NC}"
    echo "  新版本号: ${GREEN}${NEW_VERSION}${NC}"
fi

if [[ "$CUR_VERSION" == "$NEW_VERSION" ]]; then
    echo ""
    echo -e "${YELLOW}版本号未变化，跳过。${NC}"
    exit 0
fi

# ═══════════════════════════════════════════════════════════════
# 步骤 2: 更新所有配置文件的版本号
# ═══════════════════════════════════════════════════════════════

echo ""
echo -e "${BOLD}步骤 1/5: 更新版本号${NC}"
echo ""

# 备份关键文件
if [ "$DRY_RUN" = false ]; then
    BACKUP_DIR="/tmp/vansrsa-package-backup-$(date +%Y%m%d_%H%M%S)"
    mkdir -p "$BACKUP_DIR"
    cp pyproject.toml "$BACKUP_DIR/"
    cp app/settings/config.py "$BACKUP_DIR/"
    cp web/package.json "$BACKUP_DIR/"
fi

for file in pyproject.toml app/settings/config.py web/package.json; do
    replace_version_in_file "$file" "$CUR_VERSION" "$NEW_VERSION"
done

echo ""
echo -e "  备份目录: ${CYAN}${BACKUP_DIR:-[DRY-RUN]}${NC}"

# ═══════════════════════════════════════════════════════════════
# 步骤 3: 构建前端
# ═══════════════════════════════════════════════════════════════

echo ""
echo -e "${BOLD}步骤 2/5: 构建前端${NC}"
echo ""

if [ "$DRY_RUN" = false ]; then
    cd "$PROJECT_DIR/web"

    # 检查 node_modules
    if [[ ! -d "node_modules" ]]; then
        echo "  安装依赖..."
        if command -v pnpm &>/dev/null; then
            pnpm install --frozen-lockfile
        else
            echo -e "${RED}错误: pnpm 未安装。请先安装 pnpm${NC}" >&2
            exit 1
        fi
    fi

    echo "  构建中..."
    pnpm build

    if [[ $? -ne 0 ]]; then
        echo -e "${RED}错误: 前端构建失败${NC}" >&2
        exit 1
    fi

    echo -e "  ${GREEN}✓${NC} 前端构建完成"
    cd "$PROJECT_DIR"
else
    echo -e "  ${YELLOW}[DRY-RUN]${NC} 跳过前端构建"
fi

# ═══════════════════════════════════════════════════════════════
# 步骤 4: 打包
# ═══════════════════════════════════════════════════════════════

echo ""
echo -e "${BOLD}步骤 3/5: 打包项目${NC}"
echo ""

TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
ZIP_NAME="${PROJECT_NAME}_v${NEW_VERSION}_${TIMESTAMP}.zip"
mkdir -p "$OUTPUT_DIR"

if [ "$DRY_RUN" = false ]; then
    cd "$PROJECT_DIR"

    # 清理旧构建产物中可能残留的绝对路径引用
    find web/dist -name "*.html" -exec sed -i 's|/opt/VansRSA||g' {} \; 2>/dev/null || true

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
        -x "logs/*" \
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
        -x "Dev/*" \
        -x "uv.lock" \
        -x "test.json" \
        -x "test_fields_total.py" \
        -x "GEONAMES_SETUP.md"

    FILE_SIZE="$(du -h "${OUTPUT_DIR}/${ZIP_NAME}" | cut -f1)"
    echo -e "  ${GREEN}✓${NC} 打包完成"
    echo "  文件: ${OUTPUT_DIR}/${ZIP_NAME}"
    echo "  大小: ${FILE_SIZE}"
else
    echo -e "  ${YELLOW}[DRY-RUN]${NC} 输出文件: ${OUTPUT_DIR}/${ZIP_NAME}"
fi

# ═══════════════════════════════════════════════════════════════
# 步骤 5: Git 提交版本变更
# ═══════════════════════════════════════════════════════════════

echo ""
echo -e "${BOLD}步骤 4/5: Git 提交${NC}"
echo ""

if [ "$DRY_RUN" = false ]; then
    cd "$PROJECT_DIR"

    if git rev-parse --git-dir >/dev/null 2>&1; then
        git add pyproject.toml app/settings/config.py web/package.json
        git commit -m "release: ${PROJECT_NAME} v${NEW_VERSION}

Auto-incremented version from ${CUR_VERSION} to ${NEW_VERSION} (${BUMP_MODE})" 2>/dev/null || echo -e "  ${YELLOW}⚠${NC} git commit 可能已存在或无变更"

        # 打 tag
        git tag -a "v${NEW_VERSION}" -m "${PROJECT_NAME} v${NEW_VERSION}" 2>/dev/null || echo -e "  ${YELLOW}⚠${NC} tag v${NEW_VERSION} 已存在"

        echo -e "  ${GREEN}✓${NC} Git 提交完成"
        echo "  提交: release: ${PROJECT_NAME} v${NEW_VERSION}"
        echo "  标签: v${NEW_VERSION}"
    else
        echo -e "  ${YELLOW}⚠${NC} 非 Git 仓库，跳过提交"
    fi
else
    echo -e "  ${YELLOW}[DRY-RUN]${NC} git commit -m \"release: ${PROJECT_NAME} v${NEW_VERSION}\""
    echo -e "  ${YELLOW}[DRY-RUN]${NC} git tag v${NEW_VERSION}"
fi

# ═══════════════════════════════════════════════════════════════
# 完成
# ═══════════════════════════════════════════════════════════════

echo ""
echo -e "${BOLD}${GREEN}════════════════════════════════════════════════════════${NC}"
echo -e "${BOLD}${GREEN}  打包完成！${NC}"
echo -e "${BOLD}${GREEN}════════════════════════════════════════════════════════${NC}"
echo ""
if [ "$DRY_RUN" = false ]; then
    echo -e "  版本:  ${GREEN}v${NEW_VERSION}${NC} (原 ${YELLOW}${CUR_VERSION}${NC})"
    echo -e "  文件:  ${CYAN}${OUTPUT_DIR}/${ZIP_NAME}${NC}"
    echo -e "  大小:  ${FILE_SIZE}"
    echo ""
    echo -e "  ${BOLD}宿主机部署:${NC}"
    echo "    1. 将 ${ZIP_NAME} 复制到目标宿主机"
    echo "    2. unzip ${ZIP_NAME} -d /opt/VansRSA"
    echo "    3. cd /opt/VansRSA && bash vansrsa-deploy.sh"
    echo ""
    echo -e "  ${BOLD}Docker 直接部署:${NC}"
    echo "    docker compose up -d"
    echo "    访问: http://localhost:\${APP_PORT:-1110}"
    echo ""
    echo -e "  ${BOLD}回滚:${NC}"
    echo "    cp ${BACKUP_DIR}/* ${PROJECT_DIR}/"
else
    echo -e "  ${YELLOW}DRY-RUN 模式，未修改任何文件${NC}"
fi
echo ""
