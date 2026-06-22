# ============================================================
# VansRSA (Vance Road Scanner Assistant) Windows 全自动部署脚本
#
# 用法 (PowerShell):
#   .\vansrsa-deploy.ps1                      # 交互模式
#   .\vansrsa-deploy.ps1 -Install             # 首次部署 (构建 + 启动)
#   .\vansrsa-deploy.ps1 -Upgrade             # 升级 (停止 -> 重建 -> 启动, 保留数据)
#   .\vansrsa-deploy.ps1 -Start               # 仅启动
#   .\vansrsa-deploy.ps1 -Stop                # 停止
#   .\vansrsa-deploy.ps1 -Restart             # 重启
#   .\vansrsa-deploy.ps1 -Status              # 查看状态
#   .\vansrsa-deploy.ps1 -Logs                # 实时日志
#   .\vansrsa-deploy.ps1 -Health              # 健康检查
#   .\vansrsa-deploy.ps1 -Clean               # 清理容器和镜像
#
# 前置条件: Docker Desktop 17.05+
# ============================================================

param(
    [switch]$Install,
    [switch]$Upgrade,
    [switch]$Start,
    [switch]$Stop,
    [switch]$Restart,
    [switch]$Status,
    [switch]$Logs,
    [switch]$Health,
    [switch]$Clean
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

# ═══════════════════════════════════════════════════════════════
# 配置
# ═══════════════════════════════════════════════════════════════
$ProjectName   = "VansRSA"
$ProjectDesc   = "Vance Road Scanner Assistant"
$ContainerName = "VansRSA"
$ComposeFile   = "docker-compose.yml"
$AppPort       = if ($env:APP_PORT) { $env:APP_PORT } else { "1110" }

# ═══════════════════════════════════════════════════════════════
# 辅助函数
# ═══════════════════════════════════════════════════════════════

function Write-Banner {
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host "  $ProjectName 部署工具" -ForegroundColor Yellow
    Write-Host "  $ProjectDesc" -ForegroundColor Gray
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host ""
}

function Write-Ok   { param([string]$Msg) Write-Host "  [OK]    $Msg" -ForegroundColor Green }
function Write-Warn { param([string]$Msg) Write-Host "  [WARN]  $Msg" -ForegroundColor Yellow }
function Write-Err  { param([string]$Msg) Write-Host "  [ERROR] $Msg" -ForegroundColor Red; exit 1 }
function Write-Info { param([string]$Msg) Write-Host "  [..]    $Msg" -ForegroundColor Cyan }
function Write-Step { param([string]$Msg) Write-Host ""; Write-Host "  >>> $Msg" -ForegroundColor Yellow }

function Test-Docker {
    $docker = Get-Command docker -ErrorAction SilentlyContinue
    if (-not $docker) {
        Write-Err "Docker 未安装。请安装 Docker Desktop:`n        https://www.docker.com/products/docker-desktop/"
    }
    docker ps 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Write-Err "Docker 未运行。请启动 Docker Desktop。"
    }
    Write-Ok "Docker 运行正常"
}

function Test-ComposeFile {
    if (-not (Test-Path $ComposeFile)) {
        Write-Err "$ComposeFile 不存在。请在项目根目录执行此脚本。"
    }
}

function Ensure-Dirs {
    @("data", "uploads", "app\logs") | ForEach-Object {
        if (-not (Test-Path $_)) { New-Item -ItemType Directory -Path $_ -Force | Out-Null }
    }
}

# ═══════════════════════════════════════════════════════════════
# 部署操作
# ═══════════════════════════════════════════════════════════════

function Invoke-Build {
    param([bool]$NoCache = $false)
    Write-Step "构建 Docker 镜像..."
    if ($NoCache) {
        docker compose build --no-cache
    } else {
        docker compose build
    }
    if ($LASTEXITCODE -ne 0) { Write-Err "镜像构建失败" }
    Write-Ok "镜像构建成功"
}

function Invoke-Start {
    Write-Step "启动服务..."
    docker compose up -d
    if ($LASTEXITCODE -ne 0) { Write-Err "服务启动失败" }
    Write-Ok "服务已启动"
    Write-Host ""
    Write-Host "    访问地址: http://localhost:$AppPort" -ForegroundColor White
    Write-Host "    默认账号: admin" -ForegroundColor White
    Write-Host "    默认密码: 123456" -ForegroundColor White
    Write-Host ""
}

function Invoke-Stop {
    Write-Step "停止服务..."
    docker compose down
    Write-Ok "服务已停止"
}

function Invoke-Restart {
    Write-Step "重启服务..."
    $result = docker compose restart 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Warn "热重启失败，尝试完全重启..."
        docker compose down
        docker compose up -d
        if ($LASTEXITCODE -ne 0) { Write-Err "重启失败" }
        Write-Ok "服务已重启 (完全重启)"
    } else {
        Write-Ok "服务已重启"
    }
}

function Invoke-Status {
    Write-Host ""
    $running = docker ps --filter "name=$ContainerName" --format "table {{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}" 2>$null
    if ($running -match $ContainerName) {
        Write-Host $running
        Write-Host ""
        Write-Host "  访问地址: http://localhost:$AppPort" -ForegroundColor White
    } else {
        Write-Warn "服务未运行"
    }
}

function Invoke-Logs {
    Write-Step "实时日志 (Ctrl+C 退出)..."
    docker compose logs -f --tail=100
}

function Invoke-Health {
    Write-Step "健康检查..."
    $url = "http://localhost:$AppPort/"
    try {
        $response = Invoke-WebRequest -Uri $url -TimeoutSec 10 -UseBasicParsing
        if ($response.StatusCode -eq 200) {
            Write-Ok "服务健康 (HTTP $($response.StatusCode))"
        } else {
            Write-Warn "服务返回异常状态码: $($response.StatusCode)"
        }
    } catch {
        Write-Warn "服务无响应: $_"
    }
}

function Invoke-Clean {
    Write-Host ""
    Write-Warn "此操作将删除容器和镜像，但保留数据文件 (data/ uploads/ app/logs/)。"
    $confirm = Read-Host "  确认继续? [y/N]"
    if ($confirm -ne "y" -and $confirm -ne "Y") {
        Write-Host "  已取消。" -ForegroundColor Gray
        return
    }
    docker compose down 2>$null
    docker rmi vansrsa:latest 2>$null
    docker rmi "${ProjectName.ToLower()}:latest" 2>$null
    Write-Ok "清理完成 (数据已保留)"
}

function Invoke-Install {
    Write-Info "首次部署模式: 构建 -> 启动"
    Ensure-Dirs
    Invoke-Build -NoCache:$false
    Invoke-Start

    Write-Host ""
    Write-Host "========================================" -ForegroundColor Green
    Write-Host "  部署成功!" -ForegroundColor Green
    Write-Host "========================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "  访问: http://localhost:$AppPort" -ForegroundColor White
    Write-Host "  账号: admin / 123456" -ForegroundColor White
    Write-Host ""
    Write-Host "  常用命令:" -ForegroundColor Yellow
    Write-Host "    .\vansrsa-deploy.ps1 -Status   # 查看状态" -ForegroundColor Gray
    Write-Host "    .\vansrsa-deploy.ps1 -Logs     # 查看日志" -ForegroundColor Gray
    Write-Host "    .\vansrsa-deploy.ps1 -Upgrade  # 升级到新版本" -ForegroundColor Gray
    Write-Host "    .\vansrsa-deploy.ps1 -Stop     # 停止服务" -ForegroundColor Gray
    Write-Host ""
}

function Invoke-Upgrade {
    Write-Info "升级模式: 停止 -> 重新构建 -> 启动 (数据保留)"

    Write-Step "1/3 停止旧服务..."
    docker compose down

    Write-Step "2/3 重新构建镜像 (无缓存)..."
    docker compose build --no-cache
    if ($LASTEXITCODE -ne 0) { Write-Err "镜像构建失败" }

    Write-Step "3/3 启动新服务..."
    docker compose up -d
    if ($LASTEXITCODE -ne 0) { Write-Err "服务启动失败" }

    Write-Host ""
    Write-Host "========================================" -ForegroundColor Green
    Write-Host "  升级完成!" -ForegroundColor Green
    Write-Host "========================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "  访问: http://localhost:$AppPort" -ForegroundColor White
    Write-Host ""
}

# ═══════════════════════════════════════════════════════════════
# 交互模式
# ═══════════════════════════════════════════════════════════════

function Show-InteractiveMenu {
    Write-Host ""
    Write-Host "请选择操作:" -ForegroundColor Yellow
    Write-Host "  [1] 首次部署 (构建 + 启动)"
    Write-Host "  [2] 升级      (停止 -> 重建 -> 启动, 保留数据)"
    Write-Host "  [3] 仅启动"
    Write-Host "  [4] 停止"
    Write-Host "  [5] 重启"
    Write-Host "  [6] 查看状态"
    Write-Host "  [7] 查看日志"
    Write-Host "  [8] 健康检查"
    Write-Host "  [9] 清理      (删除容器/镜像, 保留数据)"
    Write-Host "  [0] 退出"
    Write-Host ""

    $choice = Read-Host "输入数字 (1-9, 0)"

    switch ($choice) {
        "1" { Invoke-Install }
        "2" { Invoke-Upgrade }
        "3" { Invoke-Start }
        "4" { Invoke-Stop }
        "5" { Invoke-Restart }
        "6" { Invoke-Status }
        "7" { Invoke-Logs }
        "8" { Invoke-Health }
        "9" { Invoke-Clean }
        "0" { Write-Host "退出。" -ForegroundColor Gray; return }
        default {
            Write-Host "无效选择，请重新输入。" -ForegroundColor Red
            Show-InteractiveMenu
        }
    }
}

# ═══════════════════════════════════════════════════════════════
# 入口
# ═══════════════════════════════════════════════════════════════

Write-Banner
Test-Docker
Test-ComposeFile

# 处理命令行参数
$hasArgs = $Install -or $Upgrade -or $Start -or $Stop -or $Restart -or $Status -or $Logs -or $Health -or $Clean

if (-not $hasArgs) {
    Show-InteractiveMenu
    exit 0
}

if ($Install)  { Invoke-Install }
if ($Upgrade)  { Invoke-Upgrade }
if ($Start)    { Invoke-Start }
if ($Stop)     { Invoke-Stop }
if ($Restart)  { Invoke-Restart }
if ($Status)   { Invoke-Status }
if ($Logs)     { Invoke-Logs }
if ($Health)   { Invoke-Health }
if ($Clean)    { Invoke-Clean }
