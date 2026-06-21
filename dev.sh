#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────
# VansRSA 开发管理脚本
# 用法: ./dev.sh {start|stop|restart|status|logs|log-clear|build}
# ──────────────────────────────────────────────────────────

set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

# ── 配置 ──
BACKEND_PORT="${BACKEND_PORT:-9999}"
FRONTEND_PORT="${FRONTEND_PORT:-3100}"
LOG_DIR="$ROOT/logs"
BACKEND_LOG="$LOG_DIR/backend.log"
FRONTEND_LOG="$LOG_DIR/frontend.log"
BACKEND_PID_FILE="$LOG_DIR/backend.pid"
FRONTEND_PID_FILE="$LOG_DIR/frontend.pid"
VENV_DIR="$ROOT/.venv"
WEB_DIR="$ROOT/web"

# ── 颜色 ──
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'
step()  { echo -e "${CYAN}➜ $*${NC}"; }
ok()    { echo -e "${GREEN}✔ $*${NC}"; }
warn()  { echo -e "${YELLOW}⚠ $*${NC}"; }
err()   { echo -e "${RED}✘ $*${NC}"; }

# ── 初始化日志目录 ──
init_logs() { mkdir -p "$LOG_DIR"; }

# ── 检查进程是否存活 ──
is_running() {
  local pid_file="$1"
  [ -f "$pid_file" ] && kill -0 "$(cat "$pid_file")" 2>/dev/null
}

# ── start: 启动前后端 ──
do_start() {
  init_logs

  # ── 启动后端 ──
  if is_running "$BACKEND_PID_FILE"; then
    warn "后端已在运行 (pid=$(cat "$BACKEND_PID_FILE"))"
  else
    step "启动后端 (port=$BACKEND_PORT) ..."
    # 激活虚拟环境再启动
    if [ -x "$VENV_DIR/bin/python" ]; then
      PYTHON="$VENV_DIR/bin/python"
    else
      PYTHON="python3"
    fi
    nohup "$PYTHON" run.py >> "$BACKEND_LOG" 2>&1 &
    echo $! > "$BACKEND_PID_FILE"
    sleep 1
    if is_running "$BACKEND_PID_FILE"; then
      ok "后端已启动 → http://localhost:$BACKEND_PORT  | 日志: $BACKEND_LOG"
    else
      err "后端启动失败，检查日志: $BACKEND_LOG"
    fi
  fi

  # ── 启动前端 ──
  if is_running "$FRONTEND_PID_FILE"; then
    warn "前端已在运行 (pid=$(cat "$FRONTEND_PID_FILE"))"
  else
    step "启动前端 (port=$FRONTEND_PORT) ..."
    cd "$WEB_DIR"
    nohup npx vite --host 0.0.0.0 --port "$FRONTEND_PORT" >> "$FRONTEND_LOG" 2>&1 &
    echo $! > "$FRONTEND_PID_FILE"
    cd "$ROOT"
    sleep 2
    if is_running "$FRONTEND_PID_FILE"; then
      ok "前端已启动 → http://localhost:$FRONTEND_PORT  | 日志: $FRONTEND_LOG"
    else
      err "前端启动失败，检查日志: $FRONTEND_LOG"
    fi
  fi

  echo ""
  echo -e "${GREEN}══════════════════════════════════════${NC}"
  echo -e "  前端: ${CYAN}http://localhost:$FRONTEND_PORT${NC}"
  echo -e "  后端: ${CYAN}http://localhost:$BACKEND_PORT${NC}"
  echo -e "  API文档: ${CYAN}http://localhost:$BACKEND_PORT/docs${NC}"
  echo -e "${GREEN}══════════════════════════════════════${NC}"
}

# ── stop: 停止前后端 ──
do_stop() {
  # 停止后端
  if is_running "$BACKEND_PID_FILE"; then
    local pid=$(cat "$BACKEND_PID_FILE")
    step "停止后端 (pid=$pid) ..."
    kill "$pid" 2>/dev/null || true
    sleep 1
    # 确保子进程也清理掉
    fuser -k "$BACKEND_PORT/tcp" 2>/dev/null || true
    pkill -f "python.*run.py" 2>/dev/null || true
    rm -f "$BACKEND_PID_FILE"
    ok "后端已停止"
  else
    # 兜底清理：按端口释放
    fuser -k "$BACKEND_PORT/tcp" 2>/dev/null && warn "已释放端口 $BACKEND_PORT" || true
  fi

  # 停止前端
  if is_running "$FRONTEND_PID_FILE"; then
    local pid=$(cat "$FRONTEND_PID_FILE")
    step "停止前端 (pid=$pid) ..."
    kill "$pid" 2>/dev/null || true
    sleep 1
    # 确保子进程也清理掉
    fuser -k "$FRONTEND_PORT/tcp" 2>/dev/null || true
    pkill -f "vite/bin/vite" 2>/dev/null || true
    rm -f "$FRONTEND_PID_FILE"
    ok "前端已停止"
  else
    fuser -k "$FRONTEND_PORT/tcp" 2>/dev/null && warn "已释放端口 $FRONTEND_PORT" || true
  fi
}

# ── restart: 重启 ──
do_restart() {
  do_stop
  sleep 1
  do_start
}

# ── status: 检查运行状态 ──
do_status() {
  local backend_ok=false frontend_ok=false
  local backend_pid="" frontend_pid=""

  if is_running "$BACKEND_PID_FILE"; then
    backend_ok=true
    backend_pid=$(cat "$BACKEND_PID_FILE")
  fi

  if is_running "$FRONTEND_PID_FILE"; then
    frontend_ok=true
    frontend_pid=$(cat "$FRONTEND_PID_FILE")
  fi

  # 如果 PID 文件不存在但进程在运行，用 ps 检查
  if ! $backend_ok; then
    local uvi_pid=$(pgrep -f "uvicorn" 2>/dev/null | head -1 || true)
    if [ -n "$uvi_pid" ]; then
      backend_ok=true
      backend_pid="$uvi_pid (孤儿，无 PID 文件)"
    fi
  fi
  if ! $frontend_ok; then
    local vite_pid=$(pgrep -f "vite/bin/vite" 2>/dev/null | head -1 || true)
    if [ -n "$vite_pid" ]; then
      frontend_ok=true
      frontend_pid="$vite_pid (孤儿，无 PID 文件)"
    fi
  fi

  echo ""
  echo -e "${CYAN}══════ 项目运行状态 ══════${NC}"
  if $backend_ok; then
    echo -e "  后端: ${GREEN}● 运行中${NC}  pid=$backend_pid  port=$BACKEND_PORT"
  else
    echo -e "  后端: ${RED}○ 未运行${NC}"
  fi
  if $frontend_ok; then
    echo -e "  前端: ${GREEN}● 运行中${NC}  pid=$frontend_pid  port=$FRONTEND_PORT"
  else
    echo -e "  前端: ${RED}○ 未运行${NC}"
  fi
  echo ""
}

# ── logs: 查看日志 ──
do_logs() {
  init_logs
  local target="${1:-both}"

  case "$target" in
    backend|be|b)
      [ -f "$BACKEND_LOG" ] || { warn "后端日志文件不存在: $BACKEND_LOG"; exit 0; }
      echo -e "${CYAN}━━━ 后端日志 ($BACKEND_LOG) ━━━${NC}"
      tail -n 50 "$BACKEND_LOG"
      ;;
    frontend|fe|f)
      [ -f "$FRONTEND_LOG" ] || { warn "前端日志文件不存在: $FRONTEND_LOG"; exit 0; }
      echo -e "${CYAN}━━━ 前端日志 ($FRONTEND_LOG) ━━━${NC}"
      tail -n 50 "$FRONTEND_LOG"
      ;;
    both|all)
      echo -e "${CYAN}━━━ 后端日志 ($BACKEND_LOG) ━━━${NC}"
      tail -n 20 "$BACKEND_LOG" 2>/dev/null || echo "(无日志)"
      echo ""
      echo -e "${CYAN}━━━ 前端日志 ($FRONTEND_LOG) ━━━${NC}"
      tail -n 20 "$FRONTEND_LOG" 2>/dev/null || echo "(无日志)"
      ;;
    tail|t|follow)
      shift 2>/dev/null || true
      echo -e "${CYAN}追踪日志输出 (Ctrl+C 退出)...${NC}"
      tail -f "$BACKEND_LOG" "$FRONTEND_LOG"
      ;;
    *)
      echo "用法: $0 logs {backend|frontend|both|tail}"
      ;;
  esac
}

# ── log-clear: 清空日志 ──
do_log_clear() {
  init_logs
  > "$BACKEND_LOG"
  > "$FRONTEND_LOG"
  ok "日志已清空"
}

# ── build: 仅构建前端产物（不启动） ──
do_build() {
  step "构建前端..."
  cd "$WEB_DIR"
  npx vite build --mode production
  cd "$ROOT"
  ok "构建完成 → $WEB_DIR/dist"
}

# ── 主入口 ──
case "${1:-start}" in
  start)   do_start ;;
  stop)    do_stop ;;
  restart) do_restart ;;
  status|st)  do_status ;;
  logs|log)   do_logs "${2:-both}" ;;
  log-clear|lc) do_log_clear ;;
  build)   do_build ;;
  *)
    echo "用法: $0 {start|stop|restart|status|logs [backend|frontend|both|tail]|log-clear|build}"
    echo ""
    echo "  start     启动前后端（后台运行，日志写入 logs/）"
    echo "  stop      停止前后端"
    echo "  restart   重启前后端"
    echo "  status    查看运行状态"
    echo "  logs      查看最近日志 (默认两端各20行)"
    echo "  logs be   查看后端日志"
    echo "  logs fe   查看前端日志"
    echo "  logs tail 实时追踪日志"
    echo "  log-clear 清空日志文件"
    echo "  build     仅构建前端产物"
    exit 1
    ;;
esac
