# ═══════════════════════════════════════════════════════════
# VansRSA 后端恢复脚本 (PowerShell)
# 从容器内备份恢复后端代码
#
# 用法:
#   .\restore-backend.ps1                  # 交互式确认
#   .\restore-backend.ps1 -Force           # 跳过确认
#   .\restore-backend.ps1 -Container MyApp # 指定容器名
# ═══════════════════════════════════════════════════════════

param(
    [string]$Container = "VansRSA",
    [switch]$Force = $false
)

$ErrorActionPreference = "Stop"
$APP_DIR    = "/opt/VansRSA/app"
$BACKUP_DIR = "/opt/VansRSA/app_backup"
$PORT       = 1110

function Write-Step($msg)  { Write-Host "[$($msg)]" -ForegroundColor Cyan }
function Write-OK($msg)    { Write-Host "  ✔ $msg" -ForegroundColor Green }
function Write-Err($msg)   { Write-Host "  ✘ $msg" -ForegroundColor Red }
function Write-Warn($msg)  { Write-Host "  ⚠ $msg" -ForegroundColor Yellow }

# ════════════════════════════════════════════
Write-Host ""
Write-Host "════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  VansRSA 后端恢复 — 从容器备份恢复" -ForegroundColor Cyan
Write-Host "════════════════════════════════════════" -ForegroundColor Cyan
Write-Host ""

# ── 1. 检查 Docker ──
Write-Step "1/5 检查 Docker"
try {
    docker version *>$null
    Write-OK "Docker 可用"
} catch {
    Write-Err "未找到 Docker，请先安装 Docker Desktop"
    Read-Host "按回车退出"
    exit 1
}

# ── 2. 检查容器 ──
Write-Step "2/5 检查容器 '$Container'"
$inspect = docker inspect $Container 2>$null | ConvertFrom-Json
if (-not $inspect) {
    Write-Err "容器 '$Container' 不存在"
    Read-Host "按回车退出"
    exit 1
}

$running = $inspect[0].State.Running
if (-not $running) {
    Write-Warn "容器未运行，正在启动..."
    docker start $Container | Out-Null
    Start-Sleep 5
}
Write-OK "容器就绪"

# ── 3. 检查备份 ──
Write-Step "3/5 检查备份"
$backupExists = docker exec $Container test -f "$BACKUP_DIR/__init__.py" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Err "备份目录 $BACKUP_DIR 不存在或为空"
    Write-Host ""
    Write-Host "可能原因：" -ForegroundColor Yellow
    Write-Host "  1. 尚未执行过热更新 (hot-update-be.sh)"
    Write-Host "  2. 上次热更新后备份已被覆盖（只保留最近一次）"
    Read-Host "按回车退出"
    exit 1
}

# 获取备份详情
$bkSize  = (docker exec $Container sh -c "du -sh $BACKUP_DIR 2>/dev/null | cut -f1") -replace '\s',''
$bkFiles = (docker exec $Container sh -c "find $BACKUP_DIR -type f 2>/dev/null | wc -l") -replace '\s',''
$bkTime  = (docker exec $Container sh -c "stat -c '%y' $BACKUP_DIR 2>/dev/null | cut -d. -f1") -replace '\s',''

Write-Host "    路径: $BACKUP_DIR"
Write-Host "    大小: $bkSize"
Write-Host "    文件: $bkFiles 个"
Write-Host "    时间: $bkTime"
Write-OK "备份有效"
Write-Host ""

# ── 4. 确认 ──
if (-not $Force) {
    Write-Step "4/5 确认操作"
    Write-Warn "即将用备份覆盖当前代码并重启容器"
    $confirm = Read-Host "    输入 y 确认恢复 [y/N]"
    if ($confirm -ne "y") {
        Write-Host "已取消。"
        exit 0
    }
} else {
    Write-Step "4/5 跳过确认 (-Force)"
}

# ── 5. 执行恢复 ──
Write-Step "5/5 执行恢复"
Write-Host "    删除当前代码..."
docker exec $Container sh -c "rm -rf $APP_DIR" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Err "删除当前代码失败"
    Read-Host "按回车退出"
    exit 1
}

Write-Host "    复制备份..."
docker exec $Container sh -c "cp -a $BACKUP_DIR $APP_DIR" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Err "复制备份失败"
    Read-Host "按回车退出"
    exit 1
}
Write-OK "代码已恢复"

Write-Host "    重启容器..."
docker restart $Container | Out-Null

# ── 6. 等待服务恢复 ──
Write-Host ""
Write-Host "等待服务恢复..." -ForegroundColor Cyan
$restored = $false
for ($i = 1; $i -le 30; $i++) {
    Start-Sleep 1
    try {
        $null = Invoke-WebRequest -Uri "http://localhost:$PORT/api/v1/base/access_token" -Method Post -Body '{"username":"admin","password":"123456"}' -ContentType "application/json" -TimeoutSec 2 -ErrorAction Stop
        Write-Host ""
        Write-Host "════════════════════════════════════════" -ForegroundColor Green
        Write-Host "  恢复完成! 服务已在 $i 秒内恢复" -ForegroundColor Green
        Write-Host "════════════════════════════════════════" -ForegroundColor Green
        $restored = $true
        break
    } catch {
        Write-Host "    等待中... ($i/30)" -ForegroundColor Gray
    }
}

if (-not $restored) {
    Write-Host ""
    Write-Warn "服务在 30 秒内未恢复，请手动检查:"
    Write-Host "  docker logs $Container"
}

Read-Host "按回车退出"
