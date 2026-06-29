@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

:: ═══════════════════════════════════════════════════════════
:: VansRSA 后端恢复脚本 (CMD)
:: 从容器内备份恢复后端代码
::
:: 用法: 双击运行，或命令行执行 restore-backend.bat
:: ═══════════════════════════════════════════════════════════

set CONTAINER=VansRSA
set APP_DIR=/opt/VansRSA/app
set BACKUP_DIR=/opt/VansRSA/app_backup

echo.
echo ════════════════════════════════════════════
echo   VansRSA 后端恢复 — 从容器备份恢复
echo ════════════════════════════════════════════
echo.

:: ── 1. 检查 Docker ──
docker version >nul 2>&1
if %errorlevel% neq 0 (
    echo [错误] 未找到 Docker，请先安装 Docker Desktop
    pause
    exit /b 1
)

:: ── 2. 检查容器状态 ──
docker inspect -f "{{.State.Running}}" %CONTAINER% >nul 2>&1
if %errorlevel% neq 0 (
    echo [错误] 容器 "%CONTAINER%" 不存在
    pause
    exit /b 1
)

for /f "tokens=*" %%a in ('docker inspect -f "{{.State.Running}}" %CONTAINER%') do set RUNNING=%%a
if not "%RUNNING%"=="true" (
    echo [警告] 容器未运行，正在启动...
    docker start %CONTAINER%
    timeout /t 5 /nobreak >nul
)

:: ── 3. 检查备份 ──
echo [1/4] 检查备份...
docker exec %CONTAINER% test -f %BACKUP_DIR%/__init__.py >nul 2>&1
if %errorlevel% neq 0 (
    echo [错误] 备份目录 %BACKUP_DIR% 不存在或为空
    echo.
    echo 可能原因：
    echo   1. 尚未执行过热更新（hot-update-be.sh）
    echo   2. 上次热更新后备份已被清理
    pause
    exit /b 1
)

:: ── 4. 显示备份信息 ──
echo [2/4] 备份信息:
for /f "tokens=*" %%a in ('docker exec %CONTAINER% sh -c "du -sh %BACKUP_DIR% 2>/dev/null | cut -f1"') do set BK_SIZE=%%a
for /f "tokens=*" %%a in ('docker exec %CONTAINER% sh -c "find %BACKUP_DIR% -type f | wc -l"') do set BK_FILES=%%a
for /f "tokens=*" %%a in ('docker exec %CONTAINER% sh -c "stat -c '%%y' %BACKUP_DIR% 2>/dev/null | cut -d. -f1"') do set BK_TIME=%%a

echo    路径: %BACKUP_DIR%
echo    大小: %BK_SIZE%
echo    文件: %BK_FILES% 个
echo    时间: %BK_TIME%
echo.

:: ── 5. 确认 ──
set /p CONFIRM="[3/4] 确认恢复? 当前代码将被覆盖 [y/N]: "
if /i not "%CONFIRM%"=="y" (
    echo 已取消。
    pause
    exit /b 0
)

:: ── 6. 执行恢复 ──
echo.
echo [4/4] 执行恢复...

docker exec %CONTAINER% sh -c "rm -rf %APP_DIR% && cp -a %BACKUP_DIR% %APP_DIR%"
if %errorlevel% neq 0 (
    echo [错误] 恢复失败
    pause
    exit /b 1
)

echo 代码已恢复，正在重启容器...
docker restart %CONTAINER%

:: ── 7. 等待服务恢复 ──
echo 等待服务恢复...
for /l %%i in (1,1,30) do (
    timeout /t 1 /nobreak >nul
    curl -s -o nul --connect-timeout 2 http://localhost:1110/api/v1/base/access_token >nul 2>&1
    if !errorlevel! equ 0 (
        echo.
        echo ════════════════════════════════════════════
        echo   恢复完成! 服务已在 %%i 秒内恢复
        echo ════════════════════════════════════════════
        pause
        exit /b 0
    )
    echo    等待中... (%%i/30)
)

echo.
echo [警告] 服务在 30 秒内未恢复，请检查 docker logs %CONTAINER%
pause
