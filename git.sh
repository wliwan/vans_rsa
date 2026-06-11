#!/usr/bin/env bash
# ============================================================
# Git 管理脚本
# 用法: bash git.sh <command> [args]
#
# 命令:
#   status          查看仓库状态
#   log [n]         查看最近 n 条提交（默认 10）
#   pull            拉取远程更新
#   push            推送本地提交
#   commit <msg>    暂存所有变更并提交
#   save   <msg>    stash 暂存当前工作区
#   pop             stash 弹出最近暂存
#   branch          列出所有分支
#   new-branch <name>  创建并切换到新分支
#   switch  <name>  切换到已有分支
#   tag             列出所有标签
#   release <v>     打版本标签并推送
#   undo            撤销最近一次提交（保留变更）
#   sync            pull --rebase + push（无冲突一键同步）
#   diff [file]     查看变更差异
# ============================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

CMD="${1:-status}"
shift 2>/dev/null || true
ARGS=("$@")

RED='\033[31m'
GREEN='\033[32m'
YELLOW='\033[33m'
BLUE='\033[34m'
BOLD='\033[1m'
NC='\033[0m'

info()  { echo -e "${BLUE}[git]${NC} $*"; }
ok()    { echo -e "${GREEN}[git]${NC} $*"; }
warn()  { echo -e "${YELLOW}[git]${NC} $*"; }
err()   { echo -e "${RED}[git]${NC} $*" >&2; }

# ── 前置检查 ──
if ! git rev-parse --is-inside-work-tree &>/dev/null; then
    err "当前目录不是 git 仓库"
    exit 1
fi

BRANCH=$(git branch --show-current)
REMOTE=$(git remote get-url origin 2>/dev/null || echo "无远程")

case "$CMD" in

status|st)
    echo -e "${BOLD}═══ Git 状态 ═══${NC}"
    echo -e "  分支: ${GREEN}${BRANCH}${NC}"
    echo -e "  远程: ${REMOTE}"
    echo ""
    git status --short
    ;;

log)
    N="${1:-10}"
    echo -e "${BOLD}═══ 最近 ${N} 条提交 ═══${NC}"
    git log --oneline --graph --decorate -"$N"
    ;;

pull)
    info "拉取远程 → origin/${BRANCH} ..."
    git pull --rebase origin "$BRANCH"
    ok "拉取完成"
    ;;

push)
    info "推送 → origin/${BRANCH} ..."
    git push origin "$BRANCH"
    ok "推送完成"
    ;;

commit|ci)
    MSG="${1:-}"
    if [ -z "$MSG" ]; then
        err "用法: bash git.sh commit \"提交信息\""
        exit 1
    fi

    if [ -z "$(git status --porcelain)" ]; then
        warn "没有需要提交的变更"
        exit 0
    fi

    echo -e "${BOLD}═══ 待提交文件 ═══${NC}"
    git status --short
    echo ""

    read -rp "确认提交以上变更？[Y/n] " confirm
    if [ "$confirm" != "Y" ] && [ "$confirm" != "y" ] && [ -n "$confirm" ]; then
        info "已取消"
        exit 0
    fi

    git add -A
    git commit -m "$MSG"
    ok "提交完成: $MSG"
    ;;

save|stash)
    MSG="${1:-WIP $(date '+%Y-%m-%d %H:%M')}"
    git stash push -u -m "$MSG"
    ok "已暂存: $MSG"
    ;;

pop)
    git stash pop
    ok "已弹出最近暂存"
    ;;

branch|br)
    echo -e "${BOLD}═══ 分支列表 ═══${NC}"
    echo -e "  当前: ${GREEN}${BRANCH}${NC}"
    echo ""
    git branch -a
    ;;

new-branch|nb)
    NAME="${1:-}"
    if [ -z "$NAME" ]; then
        err "用法: bash git.sh new-branch <分支名>"
        exit 1
    fi
    git checkout -b "$NAME"
    ok "已创建并切换到分支: $NAME"
    ;;

switch|sw)
    NAME="${1:-}"
    if [ -z "$NAME" ]; then
        err "用法: bash git.sh switch <分支名>"
        exit 1
    fi
    git checkout "$NAME"
    ok "已切换到分支: $NAME"
    ;;

tag)
    echo -e "${BOLD}═══ 标签列表 ═══${NC}"
    git tag --sort=-v:refname | head -20
    ;;

release|rel)
    VERSION="${1:-}"
    if [ -z "$VERSION" ]; then
        err "用法: bash git.sh release v0.2.0"
        exit 1
    fi

    if [ -n "$(git status --porcelain)" ]; then
        warn "有未提交的变更，请先 commit"
        git status --short
        exit 1
    fi

    git tag -a "$VERSION" -m "Release $VERSION"
    git push origin "$VERSION"
    ok "已打标签并推送: $VERSION"
    ;;

undo)
    read -rp "撤销最近一次提交，保留变更？[y/N] " confirm
    if [ "$confirm" != "y" ] && [ "$confirm" != "Y" ]; then
        info "已取消"
        exit 0
    fi
    git reset --soft HEAD~1
    ok "已撤销最近提交，变更保留在工作区"
    ;;

sync)
    info "同步: pull --rebase + push ..."
    git pull --rebase origin "$BRANCH"
    if [ -n "$(git log origin/"$BRANCH"..HEAD --oneline)" ]; then
        git push origin "$BRANCH"
    else
        info "没有本地提交需要推送"
    fi
    ok "同步完成"
    ;;

diff|d)
    if [ "${#ARGS[@]}" -gt 0 ]; then
        git diff "${ARGS[@]}"
    else
        git diff
    fi
    ;;

help|-h|--help)
    head -17 "$0"
    ;;

*)
    err "未知命令: $CMD"
    echo ""
    head -17 "$0"
    exit 1
    ;;
esac
