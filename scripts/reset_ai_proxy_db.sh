#!/bin/bash
set -e
echo "=== 1. 清理旧数据库和迁移记录 ==="
rm -rf migrations/models/
rm -f data/db.sqlite3 data/db.sqlite3-shm data/db.sqlite3-wal
echo "已清理"

echo ""
echo "=== 2. 初始化 aerich（基于新模型重建数据库） ==="
aerich init-db

echo ""
echo "=== 3. 检查是否有未应用的模型变更 ==="
aerich migrate 2>&1 || true

echo ""
echo "=== 完成 ==="
echo "数据库已重置，AI代理模型字段已全部可选"
