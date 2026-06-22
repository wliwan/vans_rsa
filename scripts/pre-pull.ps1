# ============================================================
# Windows Docker 预拉取脚本
# 解决国内镜像站 429 限流问题
#
# 用法（PowerShell 管理员运行）:
#   .\pre-pull.ps1
#
# 原理：逐层从 Docker Hub 直接拉取 base image，
#       镜像站失败时自动 fallback 到官方源。
# ============================================================

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Vance Road Scanner Assistant" -ForegroundColor Cyan
Write-Host "  预拉取 Docker Base Images" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

$images = @(
    "node:22-alpine",
    "python:3.11-slim-bullseye"
)

foreach ($img in $images) {
    Write-Host "[*] 拉取 $img ..." -ForegroundColor Yellow
    
    # 尝试直接从 Docker Hub 拉取（绕过镜像站）
    $result = docker pull $img 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "    OK" -ForegroundColor Green
        continue
    }
    
    # 回退：尝试 daocloud 镜像
    Write-Host "    直接拉取失败，尝试 daocloud 镜像..." -ForegroundColor Yellow
    $result = docker pull docker.m.daocloud.io/$img 2>&1
    if ($LASTEXITCODE -eq 0) {
        docker tag docker.m.daocloud.io/$img $img
        docker rmi docker.m.daocloud.io/$img 2>$null
        Write-Host "    OK (via daocloud)" -ForegroundColor Green
        continue
    }
    
    Write-Host "    失败，请检查网络或手动配置镜像加速" -ForegroundColor Red
    Write-Host "    Docker Desktop → 设置 → Docker Engine → 添加 registry-mirrors" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "所有 base image 就绪，可以执行 docker compose up -d" -ForegroundColor Green
