#!/usr/bin/env python3
"""
i18n 一键扫描 → 批量处理 → 编译验证流程

用法:
    # 安全模式（默认）: 只更新 cn.json，不修改源 Vue 文件
    python scripts/i18n_scan_and_process.py --proxy <AI代理名称>

    # 完整模式: 更新 cn.json 并回写源文件
    python scripts/i18n_scan_and_process.py --proxy <AI代理名称> --no-safe

    # 仅扫描预览（不处理）
    python scripts/i18n_scan_and_process.py --scan-only

    # 仅编译验证
    python scripts/i18n_scan_and_process.py --verify-only

    # 回退 git 变更
    python scripts/i18n_scan_and_process.py --rollback

流程:
    scan → 检查新字段 > 0 → AI 批量生成 key → 写入 cn.json
      → [可选: 回写源文件] → 编译验证 → [失败: git 回退]

要求:
    - 项目根目录为 Git 仓库
    - pnpm 已安装（编译验证需要）
    - AI 代理已在系统中配置
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path

# 确保项目根目录在 sys.path 中
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


async def scan_new_fields(controller) -> dict:
    """扫描前端代码，返回新字段列表。"""
    print("🔍 扫描前端代码中的硬编码中文...")
    result = await controller.scan_frontend()
    total = result["total"]
    items = result["items"]

    if total == 0:
        print("✅ 未发现新字段（所有中文已国际化或已存在 cn.json 中）")
        return result

    print(f"\n📊 发现 {total} 条待翻译字段:\n")
    # 按来源分组统计
    from collections import Counter
    by_source = Counter(it["source"] for it in items)
    by_prefix = Counter(it["prefix"] for it in items)

    print("  按来源分布:")
    for src, cnt in by_source.most_common():
        print(f"    {src:20s} {cnt} 条")
    print("\n  按模块分布 (top 10):")
    for pf, cnt in by_prefix.most_common(10):
        print(f"    {pf:40s} {cnt} 条")

    # 显示前 20 条
    print(f"\n  前 20 条:")
    for it in items[:20]:
        print(f"    [{it['source']:20s}] {it['file']}:{it['line']}  «{it['text'][:50]}»")
    if total > 20:
        print(f"    ... 还有 {total - 20} 条")

    return result


async def process_scan(controller, proxy_name: str, items: list, safe_mode: bool) -> dict:
    """调用 AI 批量生成 key 并写入 cn.json。"""
    print(f"\n🤖 使用 AI 代理 '{proxy_name}' 批量生成 key...")
    print(f"   安全模式: {'ON (只写 cn.json，不修改源文件)' if safe_mode else 'OFF (同时回写源文件)'}")
    print(f"   待处理: {len(items)} 条，分 {max(1, len(items) // 30 + 1)} 批")

    result = await controller.process_scan(
        ai_proxy_name=proxy_name,
        items=items,
        safe_mode=safe_mode,
    )

    print(f"\n📊 处理结果:")
    print(f"   扫描到: {result['scanned_count']} 条")
    print(f"   成功添加: {result['added_count']} 条")
    print(f"   已跳过: {result['skipped_count']} 条")
    print(f"   源文件替换: {result['replaced_count']} 处")
    if result.get("failed_batches"):
        print(f"   ❌ {len(result['failed_batches'])} 批次失败")
        for fb in result["failed_batches"]:
            print(f"      批次 {fb['batch']}: {fb['error'][:100]}")

    return result


def verify_build(controller) -> dict:
    """验证前端编译。"""
    print("\n🔨 验证前端编译 (pnpm build)...")
    result = controller._verify_frontend_build()

    if result["ok"]:
        print("✅ 编译通过")
    else:
        print(f"❌ 编译失败 (exit={result['exit_code']})")
        if result["stderr_tail"]:
            print(f"\n  错误输出 (最后 20 行):\n")
            for line in result["stderr_tail"].split("\n"):
                print(f"    {line}")
        if result["stdout_tail"]:
            print(f"\n  标准输出 (最后 20 行):\n")
            for line in result["stdout_tail"].split("\n"):
                print(f"    {line}")

    return result


def rollback_changes(controller) -> list:
    """回退 Git 变更。"""
    print("\n🔙 回退 Git 变更...")
    files = controller._git_modified_files()
    if not files:
        print("  没有未暂存的变更")
        return []

    print(f"  发现 {len(files)} 个已修改文件:")
    for f in files:
        print(f"    {f}")

    ok = controller._git_restore_files(files)
    if ok:
        print(f"✅ 已回退 {len(files)} 个文件")
    else:
        print("⚠ 部分回退失败")
    return files


async def main():
    parser = argparse.ArgumentParser(
        description="i18n 一键扫描 → 批量处理 → 编译验证",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python scripts/i18n_scan_and_process.py --proxy my-openai     # 安全模式全流程
  python scripts/i18n_scan_and_process.py --scan-only            # 仅扫描预览
  python scripts/i18n_scan_and_process.py --rollback             # 回退变更
""",
    )
    parser.add_argument("--proxy", help="AI 代理名称（批量处理必需）")
    parser.add_argument("--no-safe", action="store_true", help="关闭安全模式（同时回写源文件）")
    parser.add_argument("--scan-only", action="store_true", help="仅扫描预览，不处理")
    parser.add_argument("--verify-only", action="store_true", help="仅编译验证")
    parser.add_argument("--rollback", action="store_true", help="回退 Git 变更")
    parser.add_argument("--skip-verify", action="store_true", help="跳过编译验证")
    args = parser.parse_args()

    # 绕过 app/__init__.py 链式导入，直接加载 controller 文件
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "i18n_controller",
        str(PROJECT_ROOT / "app" / "controllers" / "i18n.py"),
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    controller = mod.i18n_controller

    # 仅编译验证
    if args.verify_only:
        result = verify_build(controller)
        sys.exit(0 if result["ok"] else 1)

    # 仅回退
    if args.rollback:
        rollback_changes(controller)
        return

    # 仅扫描
    if args.scan_only:
        await scan_new_fields(controller)
        return

    # 全流程
    if not args.proxy:
        print("❌ 批量处理需要指定 AI 代理: --proxy <name>")
        print("   使用 --scan-only 仅扫描预览")
        sys.exit(1)

    # 1. 扫描
    scan_result = await scan_new_fields(controller)
    if scan_result["total"] == 0:
        print("\n⚠ 没有待翻译字段，流程终止")
        print("   请确认前端代码中有未国际化的中文文本")
        return

    # 2. 批量处理
    safe_mode = not args.no_safe
    process_result = await process_scan(
        controller, args.proxy, scan_result["items"], safe_mode
    )

    if process_result["added_count"] == 0:
        print("\n⚠ 没有成功添加 key，跳过编译验证")
        return

    # 3. 编译验证
    if not args.skip_verify:
        build_result = verify_build(controller)
        if not build_result["ok"]:
            print("\n⚠ 编译失败！")
            if safe_mode:
                # 安全模式：只有 cn.json 被修改，回退它
                print("   安全模式下只有 cn.json 被修改，回退中...")
                rollback_changes(controller)
            else:
                print("   使用 --rollback 回退所有变更，或手动修复编译错误后重新处理")
            sys.exit(1)

    # 4. 成功
    print(f"\n🎯 全流程完成")
    print(f"   已添加 {process_result['added_count']} 条 key 到 cn.json")
    if safe_mode and process_result["replaced_count"] == 0:
        print(f"   安全模式: 源文件未修改。编译通过后运行以下命令回写源文件:")
        print(f"     python scripts/i18n_scan_and_process.py --proxy {args.proxy} --no-safe")


if __name__ == "__main__":
    asyncio.run(main())
