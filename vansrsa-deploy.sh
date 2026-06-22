#!/usr/bin/env bash
# ============================================================
# VansRSA (Vance Road Scanner Assistant) 宿主机全自动部署脚本
#
# 功能:
#   - 一键部署 VansRSA 到宿主机 (Linux)
#   - 支持首次部署 / 升级 / 启停 / 状态查看 / 日志 / 清理
#
# 用法:
#   bash vansrsa-deploy.sh               # 交互模式
#   bash vansrsa-deploy.sh --install     # 首次部署 (build + start)
#   bash vansrsa-deploy.sh --upgrade     # 升级 (stop → rebuild → start，保留数据)
#   bash vansrsa-deploy.sh --start       # 仅启动
#   bash vansrsa-deploy.sh --stop        # 仅停止
#   bash vansrsa-deploy.sh --restart     # 重启
#   bash vansrsa-deploy.sh --status      # 查看状态
#   bash vansrsa-deploy.sh --logs        # 查看实时日志
#   bash vansrsa-deploy.sh --clean       # 清理 (stop + remove container/image)
#
# 环境变量:
#   APP_PORT    服务端口 (默认: 1110)
#   APP_DIR     部署目录 (默认: 当前目录)
# ============================================================
set -euo pipefail

# ═══════════════════════════════════════════════════════════════
# 配置
# ═══════════════════════════════════════════════════════════════
PROJECT_NAME="VansRSA"
PROJECT_DESC="Vance Road Scanner Assistant"
CONTAINER_NAME="VansRSA"
COMPOSE_FILE="docker-compose.yml"
APP_PORT="${APP_PORT:-1110}"
APP_DIR="${APP_DIR:-$(cd "$(dirname "$0")" && pwd)}"

# ═══════════════════════════════════════════════════════════════
# 颜色
# ═══════════════════════════════════════════════════════════════
if [[ -t 1 ]]; then
    RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
    CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'
else
    RED=''; GREEN=''; YELLOW=''; CYAN=''; BOLD=''; NC=''
fi

# ═══════════════════════════════════════════════════════════════
# 辅助函数
# ═══════════════════════════════════════════════════════════════

banner() {
    echo ""
    echo -e "${BOLD}${CYAN}════════════════════════════════════════════════════════${NC}"
    echo -e "${BOLD}${CYAN}  ${PROJECT_NAME} 宿主机部署工具${NC}"
    echo -e "${BOLD}${CYAN}  ${PROJECT_DESC}${NC}"
    echo -e "${BOLD}${CYAN}════════════════════════════════════════════════════════${NC}"
    echo ""
}

ok()   { echo -e "  ${GREEN}✓${NC} $1"; }
warn() { echo -e "  ${YELLOW}⚠${NC} $1"; }
err()  { echo -e "  ${RED}✗${NC} $1"; }
info() { echo -e "  ${CYAN}→${NC} $1"; }

check_docker() {
    if ! command -v docker &>/dev/null; then
        err "Docker 未安装。请先安装 Docker (17.05+):"
        echo "    curl -fsSL https://get.docker.com | bash"
        exit 1
    fi
    if ! docker ps &>/dev/null; then
        err "Docker 未运行或当前用户无权限。请启动 Docker 并将用户加入 docker 组:"
        echo "    sudo systemctl start docker"
        echo "    sudo usermod -aG docker \$USER"
        exit 1
    fi
    ok "Docker 运行正常"
}

check_compose_file() {
    if [[ ! -f "$APP_DIR/$COMPOSE_FILE" ]]; then
        err "$COMPOSE_FILE 不存在。请在项目根目录执行此脚本。"
        exit 1
    fi
}

ensure_dirs() {
    mkdir -p "$APP_DIR/data" "$APP_DIR/uploads" "$APP_DIR/app/logs"
}

# ═══════════════════════════════════════════════════════════════
# 核心操作
# ═══════════════════════════════════════════════════════════════

do_build() {
    local nocache="${1:-false}"
    echo ""
    info "开始构建 Docker 镜像..."
    cd "$APP_DIR"
    if [[ "$nocache" == "true" ]]; then
        docker compose build --no-cache
    else
        docker compose build
    fi
    if [[ $? -ne 0 ]]; then
        err "镜像构建失败"
        exit 1
    fi
    ok "镜像构建成功"
}

do_start() {
    echo ""
    info "启动服务..."
    cd "$APP_DIR"
    docker compose up -d
    if [[ $? -ne 0 ]]; then
        err "服务启动失败"
        exit 1
    fi
    ok "服务已启动"
    echo ""
    echo -e "  ${BOLD}访问地址:${NC}  http://localhost:${APP_PORT}"
    echo -e "  ${BOLD}默认账号:${NC}  admin"
    echo -e "  ${BOLD}默认密码:${NC}  123456"
    echo ""
}

do_stop() {
    echo ""
    info "停止服务..."
    cd "$APP_DIR"
    docker compose down
    ok "服务已停止"
}

do_restart() {
    echo ""
    info "重启服务..."
    cd "$APP_DIR"
    if docker compose restart 2>/dev/null; then
        ok "服务已重启"
    else
        warn "热重启失败，尝试完全重启..."
        docker compose down
        docker compose up -d
        ok "服务已重启 (完全重启)"
    fi
}

do_status() {
    echo ""
    cd "$APP_DIR"
    if docker ps --filter "name=${CONTAINER_NAME}" --format "table {{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}" 2>/dev/null | grep -q "$CONTAINER_NAME"; then
        docker ps --filter "name=${CONTAINER_NAME}" --format "table {{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}"
        echo ""
        echo -e "  ${BOLD}访问地址:${NC} http://localhost:${APP_PORT}"
    else
        warn "服务未运行"
    fi
}

do_logs() {
    echo ""
    info "查看实时日志 (Ctrl+C 退出)..."
    cd "$APP_DIR"
    docker compose logs -f --tail=100
}

do_clean() {
    echo ""
    warn "此操作将删除容器和镜像，但保留数据文件 (data/uploads/logs)。"
    read -r -p "  确认继续? [y/N]: " confirm
    if [[ ! "$confirm" =~ ^[Yy]$ ]]; then
        echo "  已取消。"
        return
    fi
    cd "$APP_DIR"
    docker compose down 2>/dev/null || true
    docker rmi vansrsa:latest 2>/dev/null || true
    docker rmi "${CONTAINER_NAME,,}:latest" 2>/dev/null || true
    ok "清理完成 (数据已保留)"
}

do_install() {
    echo ""
    info "首次部署模式: 构建 → 启动"
    ensure_dirs
    do_build "false"
    do_start

    echo ""
    echo -e "${BOLD}${GREEN}════════════════════════════════════════════════════════${NC}"
    echo -e "${BOLD}${GREEN}  部署成功！${NC}"
    echo -e "${BOLD}${GREEN}════════════════════════════════════════════════════════${NC}"
    echo ""
    echo -e "  ${BOLD}访问:${NC}  http://localhost:${APP_PORT}"
    echo -e "  ${BOLD}账号:${NC}  admin / 123456"
    echo ""
    echo -e "  ${BOLD}常用命令:${NC}"
    echo "    bash vansrsa-deploy.sh --status    # 查看状态"
    echo "    bash vansrsa-deploy.sh --logs      # 查看日志"
    echo "    bash vansrsa-deploy.sh --upgrade   # 升级到新版本"
    echo "    bash vansrsa-deploy.sh --stop      # 停止服务"
    echo ""
}

do_upgrade() {
    echo ""
    info "升级模式: 停止 → 重新构建 → 启动 (数据保留)"
    cd "$APP_DIR"

    # 1. 停止
    echo ""
    info "1/3 停止旧服务..."
    docker compose down

    # 2. 构建
    echo ""
    info "2/3 重新构建镜像..."
    docker compose build --no-cache

    # 3. 启动
    echo ""
    info "3/3 启动新服务..."
    docker compose up -d

    echo ""
    echo -e "${BOLD}${GREEN}════════════════════════════════════════════════════════${NC}"
    echo -e "${BOLD}${GREEN}  升级完成！${NC}"
    echo -e "${BOLD}${GREEN}════════════════════════════════════════════════════════${NC}"
    echo ""
    echo -e "  ${BOLD}访问:${NC}  http://localhost:${APP_PORT}"
    echo ""
}

do_health() {
    echo ""
    info "健康检查..."
    local url="http://localhost:${APP_PORT}/"
    if command -v curl &>/dev/null; then
        if curl -sf -o /dev/null -w "%{http_code}" "$url" 2>/dev/null | grep -q "200\|302\|301"; then
            ok "服务健康 (响应正常)"
        else
            warn "服务无响应，请检查状态"
        fi
    else
        warn "curl 未安装，跳过健康检查"
    fi
}

# ═══════════════════════════════════════════════════════════════
# 交互模式
# ═══════════════════════════════════════════════════════════════

interactive_mode() {
    echo ""
    echo -e "${YELLOW}请选择操作:${NC}"
    echo "  [1] 首次部署 (构建 + 启动)"
    echo "  [2] 升级      (停止 → 重建 → 启动, 保留数据)"
    echo "  [3] 仅启动"
    echo "  [4] 停止"
    echo "  [5] 重启"
    echo "  [6] 查看状态"
    echo "  [7] 查看日志"
    echo "  [8] 健康检查"
    echo "  [9] 清理 (停止 + 删除容器/镜像, 保留数据)"
    echo "  [0] 退出"
    echo ""
    read -r -p "输入数字 (1-9, 0): " choice

    case "$choice" in
        1) do_install ;;
        2) do_upgrade ;;
        3) do_start ;;
        4) do_stop ;;
        5) do_restart ;;
        6) do_status ;;
        7) do_logs ;;
        8) do_health ;;
        9) do_clean ;;
        0) echo "退出。"; exit 0 ;;
        *) echo -e "${RED}无效选择${NC}"; interactive_mode ;;
    esac
}

# ═══════════════════════════════════════════════════════════════
# 入口
# ═══════════════════════════════════════════════════════════════

banner
check_docker
check_compose_file
cd "$APP_DIR"

# 解析参数
if [[ $# -eq 0 ]]; then
    interactive_mode
    exit 0
fi

while [[ $# -gt 0 ]]; do
    case "$1" in
        --install|-i)  do_install;   exit 0 ;;
        --upgrade|-u)  do_upgrade;   exit 0 ;;
        --start|-s)    do_start;     exit 0 ;;
        --stop|-S)     do_stop;      exit 0 ;;
        --restart|-r)  do_restart;   exit 0 ;;
        --status|-t)   do_status;    exit 0 ;;
        --logs|-l)     do_logs;      exit 0 ;;
        --clean|-c)    do_clean;     exit 0 ;;
        --health|-H)   do_health;    exit 0 ;;
        -h|--help)
            echo "用法: bash vansrsa-deploy.sh [选项]"
            echo ""
            echo "选项:"
            echo "  (无参数)       交互模式"
            echo "  --install, -i  首次部署 (构建 + 启动)"
            echo "  --upgrade, -u  升级 (停止 → 重建 → 启动, 保留数据)"
            echo "  --start, -s    仅启动服务"
            echo "  --stop, -S     停止服务"
            echo "  --restart, -r  重启服务"
            echo "  --status, -t   查看状态"
            echo "  --logs, -l     查看实时日志"
            echo "  --health, -H   健康检查"
            echo "  --clean, -c    清理容器和镜像 (保留数据)"
            echo "  -h, --help     显示帮助"
            echo ""
            echo "环境变量:"
            echo "  APP_PORT       服务端口 (默认: 1110)"
            echo "  APP_DIR        部署目录 (默认: 当前目录)"
            exit 0
            ;;
        *) err "未知参数: $1"; echo "使用 -h 查看帮助"; exit 1 ;;
    esac
done
