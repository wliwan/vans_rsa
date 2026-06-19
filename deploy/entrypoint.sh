#!/bin/sh
set -e

echo "========================================"
echo "  VansRSA Entrypoint"
echo "========================================"

# ── 确保数据目录存在 ──
mkdir -p data

# ── 数据库迁移 ──
echo "[1/3] 执行数据库迁移..."
AERICH_TIMEOUT=120
if [ -d "migrations/models" ] && [ "$(ls -A migrations/models 2>/dev/null)" ]; then
    set +e
    timeout ${AERICH_TIMEOUT} aerich upgrade 2>/dev/null
    AERICH_EXIT=$?
    set -e
    if [ $AERICH_EXIT -eq 0 ]; then
        echo "✅ 数据库迁移完成"
    elif [ $AERICH_EXIT -eq 124 ]; then
        echo "⚠️  数据库迁移超时（${AERICH_TIMEOUT}秒），可能已完成，继续启动..."
    else
        echo "⚠️  数据库迁移失败（exit=$AERICH_EXIT），尝试初始化..."
        set +e
        timeout 60 aerich init-db 2>/dev/null
        set -e
        echo "⚠️  初始化完成（忽略错误），继续启动..."
    fi
else
    echo "⚠️  未找到迁移文件，尝试初始化数据库..."
    set +e
    timeout 60 aerich init-db 2>/dev/null
    set -e
    echo "⚠️  初始化完成（忽略错误），继续启动..."
fi

echo "[2/3] 启动 Nginx..."
nginx

echo "[3/3] 启动 FastAPI 服务 (0.0.0.0:9999)..."
echo "========================================"

exec python run.py
