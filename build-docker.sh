#!/usr/bin/env bash
# ============================================================
# Docker 镜像构建脚本
# 用法: bash build-docker.sh [OPTIONS] [tag]
#
# OPTIONS:
#   --skip-web    跳过 Dockerfile 内的前端构建（需预先 bash build-web.sh）
#   --no-cache    强制无缓存构建（默认行为）
#   tag           镜像标签，默认 latest
#
# 示例:
#   bash build-docker.sh                  # 完整构建 → vue-fastapi-admin:latest
#   bash build-docker.sh 0.2.0            # 指定版本号
#   bash build-docker.sh --skip-web       # 跳过前端构建（已手动构建过 web/dist/）
# ============================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# ── 解析参数 ──
SKIP_WEB=false
NO_CACHE="--no-cache"
TAG="latest"
DOCKERFILE="Dockerfile"
for arg in "$@"; do
    case "$arg" in
        --skip-web) SKIP_WEB=true ;;
        --no-cache) NO_CACHE="--no-cache" ;;
        --cache)    NO_CACHE="" ;;
        *)          TAG="$arg" ;;
    esac
done

# ── 预构建模式校验 ──
if [ "$SKIP_WEB" = true ]; then
    DOCKERFILE="Dockerfile.prebuilt"
    if [ ! -d "web/dist" ]; then
        echo "❌ web/dist/ 不存在，请先执行: bash build-web.sh"
        exit 1
    fi
    echo "  使用预构建前端: web/dist/ ($(du -sh web/dist | cut -f1))"
fi

# ── 配置 ──
APP_NAME="vue-fastapi-admin"
APP_VERSION=$(sed -n 's/^ *version.*=.*"\([^"]*\)".*/\1/p' pyproject.toml)
IMAGE="${APP_NAME}:${TAG}"
LATEST_IMAGE="${APP_NAME}:latest"

# ── 检测容器运行时: docker > podman ──
if command -v docker &>/dev/null; then
    RUNTIME="docker"
elif command -v podman &>/dev/null; then
    RUNTIME="podman"
else
    echo "❌ 未找到 docker 或 podman"
    exit 1
fi

echo "========================================"
echo "  ${APP_NAME} Docker 镜像构建"
echo "========================================"
echo ""
echo "  容器运行时:  ${RUNTIME}"
echo "  版本号:      ${APP_VERSION}"
echo "  镜像标签:    ${IMAGE}"
echo "  跳过前端构建: ${SKIP_WEB}"
echo "  无缓存:      ${NO_CACHE:+是}"
echo ""

# ── 构建 ──
echo "🔨 开始构建镜像 (${DOCKERFILE})..."
${RUNTIME} build ${NO_CACHE} -f "${DOCKERFILE}" -t "${IMAGE}" .

# 如果 tag 不是 latest，同时打 latest 标签
if [ "${TAG}" != "latest" ]; then
    ${RUNTIME} tag "${IMAGE}" "${LATEST_IMAGE}"
    echo "🏷️  已打标签: ${LATEST_IMAGE}"
fi

echo ""
echo "========================================"
echo "  ✅ 镜像构建完成"
echo "========================================"
echo ""
echo "  镜像列表:"
${RUNTIME} images --format "table {{.Repository}}\t{{.Tag}}\t{{.Size}}" 2>/dev/null | grep -E "REPOSITORY|${APP_NAME}" || ${RUNTIME} images | grep "${APP_NAME}" || true
echo ""
echo "  启动容器:"
echo "    ${RUNTIME} run -d --restart=always --name=${APP_NAME} -p 80:80 ${IMAGE}"
echo ""
echo "  查看日志:"
echo "    ${RUNTIME} logs -f ${APP_NAME}"
