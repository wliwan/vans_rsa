#!/bin/sh
set -e

echo "========================================"
echo "  Vue-FastAPI-Admin Entrypoint"
echo "========================================"

# ── 数据库迁移 ──
echo "[1/3] 执行数据库迁移..."
if [ -d "migrations/models" ] && [ "$(ls -A migrations/models 2>/dev/null)" ]; then
    aerich upgrade 2>/dev/null || {
        echo "⚠️  数据库迁移失败，尝试初始化..."
        aerich init-db 2>/dev/null || echo "⚠️  初始化也失败了，跳过迁移步骤"
    }
else
    echo "⚠️  未找到迁移文件，尝试初始化数据库..."
    aerich init-db 2>/dev/null || echo "⚠️  初始化失败，跳过迁移步骤"
fi

echo "[2/3] 启动 Nginx..."
nginx

echo "[3/3] 启动 FastAPI 服务 (0.0.0.0:9999)..."
echo "========================================"

exec python run.py
