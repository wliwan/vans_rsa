# ============================================================
# Vance Road Scanner Assistant 打包脚本 (Windows PowerShell)
#
# 用法:
#   .\package.ps1              # 打包为 deploy.zip
#   .\package.ps1 -Name v1.0   # 打包为 vance-road-scanner-v1.0.zip
#
# 排除: node_modules, .git, __pycache__, dist, db.sqlite3 等
# ============================================================

param(
    [string]$Name = "deploy"
)

$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$OutputFile  = Join-Path $ProjectRoot "vance-road-scanner-$Name.zip"

# ── 排除规则 ──
$ExcludePatterns = @(
    # Python
    "**/__pycache__/**",
    "**/*.pyc",
    "**/*.pyo",
    "**/.venv/**",
    "**/venv/**",
    "**/.pytest_cache/**",
    "**/.mypy_cache/**",
    "**/.ruff_cache/**",
    "**/*.egg-info/**",

    # Node / 前端
    "**/node_modules/**",
    "**/web/dist/**",
    "**/web/.env",
    "**/web/.env.*",
    "**/.npm/**",

    # Git
    "**/.git/**",
    "**/.gitattributes",
    "**/.gitignore",

    # IDE
    "**/.idea/**",
    "**/.vscode/**",
    "**/*.swp",
    "**/*.swo",
    "**/*~",
    "**/.DS_Store",

    # DB / Cache
    "**/db.sqlite3*",
    "**/cache/**",
    "**/*.log",

    # Docker 自身（构建产物不打入源码包）
    "**/Dockerfile*",
    "**/docker-compose*.yml",
    "**/.dockerignore",

    # 杂项
    "**/test.json",
    "**/uv.lock",
    "**/stats.html"
)

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Vance Road Scanner Assistant" -ForegroundColor Cyan
Write-Host "  项目打包" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "  输出文件: $OutputFile" -ForegroundColor Yellow
Write-Host ""

# ── 生成排除文件列表 ──
$ExcludeFile = Join-Path $env:TEMP "vrsa_package_exclude.txt"
$ExcludePatterns | Out-File -FilePath $ExcludeFile -Encoding UTF8

# ── 打包 ──
Write-Host "[*] 正在打包..." -ForegroundColor Yellow

Push-Location $ProjectRoot
try {
    # 删除旧文件
    if (Test-Path $OutputFile) {
        Remove-Item $OutputFile -Force
    }

    # 收集文件（排除 gitignore 规则 + 自定义排除）
    $files = Get-ChildItem -Recurse -File |
        Where-Object {
            $full = $_.FullName.Replace("$ProjectRoot\", "").Replace("\", "/")
            foreach ($p in $ExcludePatterns) {
                # 支持 ** 通配
                $regex = "^" + [regex]::Escape($p).Replace("\*\*", ".*").Replace("\*", "[^/]*") + "$"
                if ($full -match $regex) { return $false }
            }
            return $true
        }

    if (-not $files) {
        Write-Host "  没有找到可打包的文件" -ForegroundColor Red
        exit 1
    }

    # 按目录分组并压缩
    $total = $files.Count
    $current = 0

    $files | Compress-Archive -DestinationPath $OutputFile -CompressionLevel Optimal

    $size = [math]::Round((Get-Item $OutputFile).Length / 1MB, 1)
    Write-Host ""
    Write-Host "  ✅ 打包完成" -ForegroundColor Green
    Write-Host "  文件: $OutputFile" -ForegroundColor White
    Write-Host "  大小: ${size} MB" -ForegroundColor White
    Write-Host "  文件数: $total" -ForegroundColor White
}
catch {
    Write-Host "  ❌ 打包失败: $_" -ForegroundColor Red
    exit 1
}
finally {
    Pop-Location
    if (Test-Path $ExcludeFile) { Remove-Item $ExcludeFile -Force }
}
