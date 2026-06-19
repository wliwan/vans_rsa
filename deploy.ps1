# ============================================================
# VansRSA Windows Deployment Script
#
# Usage (PowerShell):
#   .\deploy.ps1                  # Build image + start service
#   .\deploy.ps1 -NoCache         # Force no-cache build + start
#   .\deploy.ps1 -Start           # Start only (image already built)
#   .\deploy.ps1 -Build           # Build only, don't start
#   .\deploy.ps1 -Stop            # Stop service
#   .\deploy.ps1 -Restart         # Restart service
#   .\deploy.ps1 -Logs            # View live logs
#   .\deploy.ps1 -Status          # View service status
#   .\deploy.ps1 -Clean           # Stop + remove container & image
#   .\deploy.ps1 -Upgrade         # Stop > rebuild > start (keeps data)
# ============================================================

param(
    [switch]$NoCache,
    [switch]$Start,
    [switch]$Build,
    [switch]$Stop,
    [switch]$Restart,
    [switch]$Logs,
    [switch]$Status,
    [switch]$Clean,
    [switch]$Upgrade
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

$ContainerName = "VansRSA"
$ComposeFile   = "docker-compose.yml"
$AppPort       = if ($env:APP_PORT) { $env:APP_PORT } else { "1110" }

# ═══════════════════════════════════════════════════════════════
# Helper Functions
# ═══════════════════════════════════════════════════════════════

function Write-Banner {
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host "  VansRSA Deploy Tool" -ForegroundColor Yellow
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host ""
}

function Test-Docker {
    $docker = Get-Command docker -ErrorAction SilentlyContinue
    if (-not $docker) {
        Write-Host "[ERROR] Docker not found. Install Docker Desktop first:" -ForegroundColor Red
        Write-Host "        https://www.docker.com/products/docker-desktop/" -ForegroundColor Gray
        exit 1
    }
    docker ps 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[ERROR] Docker is not running. Start Docker Desktop." -ForegroundColor Red
        exit 1
    }
    Write-Host "[OK] Docker is running" -ForegroundColor Green
}

function Test-ComposeFile {
    if (-not (Test-Path $ComposeFile)) {
        Write-Host "[ERROR] $ComposeFile not found." -ForegroundColor Red
        Write-Host "        Run this script from the project root directory." -ForegroundColor Gray
        exit 1
    }
}

function Invoke-Build {
    param([bool]$nocache = $false)
    Write-Host ""
    Write-Host "[BUILD] Starting image build..." -ForegroundColor Yellow
    if ($nocache) {
        docker compose build --no-cache
    } else {
        docker compose build
    }
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[ERROR] Build failed" -ForegroundColor Red
        exit 1
    }
    Write-Host "[OK] Image built successfully" -ForegroundColor Green
}

function Invoke-Start {
    Write-Host ""
    Write-Host "[START] Starting service..." -ForegroundColor Yellow
    docker compose up -d
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[ERROR] Start failed" -ForegroundColor Red
        exit 1
    }
    Write-Host "[OK] Service is running" -ForegroundColor Green
    Write-Host ""
    Write-Host "    URL:      http://localhost:$AppPort" -ForegroundColor White
    Write-Host "    Username: admin" -ForegroundColor White
    Write-Host "    Password: 123456" -ForegroundColor White
    Write-Host ""
}

function Invoke-Stop {
    Write-Host "[STOP] Stopping service..." -ForegroundColor Yellow
    docker compose down
    Write-Host "[OK] Service stopped" -ForegroundColor Green
}

function Invoke-Restart {
    Write-Host "[RESTART] Restarting service..." -ForegroundColor Yellow
    docker compose restart
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[WARN] Restart failed, attempting full restart..." -ForegroundColor Yellow
        docker compose down
        Invoke-Build
        Invoke-Start
    } else {
        Write-Host "[OK] Service restarted" -ForegroundColor Green
    }
}

function Invoke-Logs {
    docker compose logs -f
}

function Invoke-Status {
    Write-Host ""
    docker ps --filter "name=$ContainerName" --format "table {{.Names}}`t{{.Image}}`t{{.Status}}`t{{.Ports}}"
    Write-Host ""
    Write-Host "URL: http://localhost:$AppPort" -ForegroundColor White
}

function Invoke-Clean {
    Write-Host "[WARN] This will remove the container and image." -ForegroundColor Yellow
    Write-Host "       Data files (data/ and uploads/) will be kept." -ForegroundColor Gray
    Write-Host "       Continue? (y/N)" -ForegroundColor Yellow
    $confirm = Read-Host
    if ($confirm -ne "y" -and $confirm -ne "Y") {
        Write-Host "Cancelled." -ForegroundColor Gray
        return
    }
    docker compose down
    docker rmi vansrsa:latest 2>$null
    Write-Host "[OK] Cleanup complete (data preserved)" -ForegroundColor Green
}

function Invoke-Upgrade {
    Write-Host "[UPGRADE] Upgrading deployment..." -ForegroundColor Yellow
    Write-Host "         1/3 Stopping old service..."
    docker compose down
    Write-Host "         2/3 Rebuilding image..."
    docker compose build --no-cache
    Write-Host "         3/3 Starting new service..."
    docker compose up -d
    Write-Host "[OK] Upgrade complete" -ForegroundColor Green
    Write-Host ""
    Write-Host "    URL: http://localhost:$AppPort" -ForegroundColor White
}

# ═══════════════════════════════════════════════════════════════
# Entry
# ═══════════════════════════════════════════════════════════════

Write-Banner
Test-Docker
Test-ComposeFile

switch ($true) {
    $Clean    { Invoke-Clean; break }
    $Logs     { Invoke-Logs; break }
    $Status   { Invoke-Status; break }
    $Stop     { Invoke-Stop; break }
    $Restart  { Invoke-Restart; break }
    $Build    { Invoke-Build -nocache:$NoCache; break }
    $Start    { Invoke-Start; break }
    $Upgrade  { Invoke-Upgrade; break }
    default   {
        Invoke-Build -nocache:$NoCache
        Invoke-Start
        Write-Host "Tip: use .\deploy.ps1 -Logs to view live logs" -ForegroundColor Gray
    }
}
