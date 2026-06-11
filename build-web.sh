#!/usr/bin/env bash
# ============================================================
# 前端构建脚本
# 用法: bash build-web.sh
# 输出: web/dist/
# ============================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "========================================"
echo "  Vue-FastAPI-Admin 前端构建"
echo "========================================"

cd web

# ── 检测 Node.js ──
if ! command -v node &>/dev/null; then
    echo "❌ 未找到 Node.js，请先安装 Node.js >= 18.8.0"
    exit 1
fi

NODE_VERSION=$(node -v | sed 's/^v//')
echo "  Node.js: v${NODE_VERSION}"

# ── 检测包管理器: pnpm > npm ──
if command -v pnpm &>/dev/null; then
    PKG_MGR="pnpm"
elif command -v npm &>/dev/null; then
    echo "⚠️  未找到 pnpm，使用 npm（建议: npm i -g pnpm）"
    PKG_MGR="npm"
else
    echo "❌ 未找到 pnpm 或 npm"
    exit 1
fi

echo "  包管理器: ${PKG_MGR}"
echo ""

# ── 安装依赖 ──
echo "📦 安装依赖..."
if [ "$PKG_MGR" = "pnpm" ]; then
    pnpm install --frozen-lockfile
else
    npm ci 2>/dev/null || npm install
fi

# ── 编译 ──
echo ""
echo "🔨 编译前端..."
if [ "$PKG_MGR" = "pnpm" ]; then
    pnpm build
else
    npm run build
fi

echo ""
echo "========================================"
echo "  ✅ 前端构建完成 → web/dist/"
echo "========================================"
