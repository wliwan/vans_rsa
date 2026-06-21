#!/usr/bin/env python3
"""
i18n 自动翻译脚本 — 根据 cn.json 翻译/补全其他语言包。

用法:
  python3 scripts/i18n_translate.py en                        # 补全 en.json 缺失的翻译
  python3 scripts/i18n_translate.py ja --create               # 创建全新的日文翻译文件
  python3 scripts/i18n_translate.py ko --module views.statistic-center  # 只翻译指定模块
  python3 scripts/i18n_translate.py en --force                 # 强制重新翻译所有条目
  python3 scripts/i18n_translate.py list                       # 列出支持的语言

翻译 API: MyMemory (免费，无需密钥) + 有道 suggest (短词降级)
"""

import json
import re
import sys
import time
import hashlib
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
I18N_DIR = PROJECT_ROOT / 'web' / 'i18n' / 'messages'
CN_FILE = I18N_DIR / 'cn.json'

# MyMemory 语言名映射
LANG_MAP = {
    'en': 'english',
    'ja': 'japanese',
    'ko': 'korean',
    'fr': 'french',
    'de': 'german',
    'es': 'spanish',
    'ru': 'russian',
    'tr': 'turkish',
    'pt': 'portuguese',
    'it': 'italian',
    'th': 'thai',
    'vi': 'vietnamese',
    'ar': 'arabic',
    'nl': 'dutch',
    'pl': 'polish',
    'sv': 'swedish',
}

def list_languages():
    print("Supported languages (MyMemory):")
    for code, name in sorted(LANG_MAP.items()):
        fn = I18N_DIR / f'{code}.json'
        exists = '✅' if fn.exists() else '➕'
        print(f"  {exists} {code} = {name}")

def load_json(path):
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_json(path, data):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def find_missing_keys(cn_data, target_data, module_path=None):
    """找出 cn 中有但 target 中没有的 key 路径。"""
    missing = {}

    def walk(d_cn, d_target, prefix=''):
        for key, val in d_cn.items():
            full_key = f'{prefix}.{key}' if prefix else key
            if isinstance(val, dict):
                t = d_target.get(key, {}) if isinstance(d_target, dict) else {}
                walk(val, t, full_key)
            elif isinstance(val, str) and re.search(r'[\u4e00-\u9fff]', val):
                # 只翻译包含中文的字符串
                if module_path and not full_key.startswith(module_path):
                    continue
                if isinstance(d_target, dict) and key in d_target:
                    continue  # 已存在
                missing[full_key] = val

    walk(cn_data, target_data)
    return missing

def mymemory_translate(text, target_lang):
    """使用 MyMemory API 翻译。"""
    try:
        from deep_translator import MyMemoryTranslator
        result = MyMemoryTranslator(
            source='chinese simplified',
            target=target_lang
        ).translate(text)
        return result if result and result != text else None
    except Exception:
        return None

def youdao_suggest(text):
    """有道词典 suggest API（短词降级）。"""
    if len(text) > 8:
        return None
    try:
        import requests
        resp = requests.get(
            'https://dict.youdao.com/suggest',
            params={'num': 1, 'ver': '3.0', 'doctype': 'json', 'cache': 'false', 'le': 'en', 'q': text},
            timeout=5
        )
        data = resp.json()
        if data.get('result', {}).get('code') == 200:
            entries = data.get('data', {}).get('entries', [])
            if entries:
                return entries[0].get('explain', '').split(';')[0].strip()
    except Exception:
        pass
    return None

def translate_text(text, target_lang_code, target_lang_name):
    """翻译单个文本，多层降级。"""
    # 1. MyMemory
    result = mymemory_translate(text, target_lang_name)
    if result:
        return result
    time.sleep(1.2)
    
    # 2. 有道 suggest (仅短词，且目标为英文时有效)
    if target_lang_code == 'en':
        result = youdao_suggest(text)
        if result:
            return result
    
    # 3. 返回原文（标记为待翻译）
    return f'[TODO] {text}'

def deep_set(d, key_path, value):
    """按点分隔路径设置嵌套字典值。"""
    parts = key_path.split('.')
    for part in parts[:-1]:
        if part not in d:
            d[part] = {}
        d = d[part]
    d[parts[-1]] = value

def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return

    lang = sys.argv[1]

    if lang == 'list':
        list_languages()
        return

    if lang not in LANG_MAP:
        print(f"❌ 不支持的语言: {lang}")
        print(f"   支持: {', '.join(sorted(LANG_MAP.keys()))}")
        print(f"   运行 'list' 查看完整列表")
        return

    # 解析参数
    force = '--force' in sys.argv
    create = '--create' in sys.argv
    module = None
    for i, arg in enumerate(sys.argv):
        if arg == '--module' and i + 1 < len(sys.argv):
            module = sys.argv[i + 1]

    target_file = I18N_DIR / f'{lang}.json'
    lang_name = LANG_MAP[lang]

    # 加载源文件
    print(f"📖 加载 cn.json ...")
    cn_data = load_json(CN_FILE)

    # 加载或创建目标文件
    if target_file.exists():
        target_data = load_json(target_file)
        print(f"📖 加载 {lang}.json (现有 {_count_keys(target_data)} keys)")
    elif create:
        target_data = {}
        print(f"🆕 创建新文件 {lang}.json")
    else:
        print(f"❌ {lang}.json 不存在。使用 --create 创建新文件。")
        return

    # 找出缺失的 key
    if force:
        # 重新翻译所有中文条目
        print("🔄 --force: 重新翻译所有条目")
        missing = {}
        def walk_all(d, prefix=''):
            for k, v in d.items():
                full = f'{prefix}.{k}' if prefix else k
                if isinstance(v, dict):
                    walk_all(v, full)
                elif isinstance(v, str) and re.search(r'[\u4e00-\u9fff]', v):
                    if module and not full.startswith(module):
                        continue
                    missing[full] = v
        walk_all(cn_data)
    else:
        missing = find_missing_keys(cn_data, target_data, module)

    if not missing:
        print("✅ 所有 key 已翻译，无需处理")
        return

    print(f"\n🔍 发现 {len(missing)} 个缺失翻译")
    print(f"🌐 目标语言: {lang_name} ({lang})")
    if module:
        print(f"📦 模块过滤: {module}")
    print(f"⏱️  预计耗时: ~{len(missing) * 1.5:.0f} 秒\n")

    # 逐条翻译
    translated = 0
    failed = 0
    for i, (key_path, text) in enumerate(missing.items(), 1):
        short_text = text[:50] + ('...' if len(text) > 50 else '')
        print(f"  [{i}/{len(missing)}] {key_path[-60:]}")
        print(f"         zh: {short_text}")

        result = translate_text(text, lang, lang_name)
        if result and not result.startswith('[TODO]'):
            deep_set(target_data, key_path, result)
            translated += 1
            print(f"         {lang}: {result[:60]}")
        else:
            failed += 1
            print(f"         {lang}: ⚠️ 翻译失败，保留原文")

        # 每 10 条保存一次
        if i % 10 == 0:
            save_json(target_file, target_data)
            print(f"         💾 已保存 ({i}/{len(missing)})")

    # 最终保存
    save_json(target_file, target_data)

    print(f"\n{'='*50}")
    print(f"✅ 完成: {translated} 条翻译成功, {failed} 条失败")
    print(f"📄 已写入: {target_file}")
    print(f"📊 {lang}.json 总计 {_count_keys(target_data)} keys")

def _count_keys(d, prefix=''):
    cnt = 0
    for v in d.values():
        if isinstance(v, dict):
            cnt += _count_keys(v)
        elif isinstance(v, str):
            cnt += 1
    return cnt

if __name__ == '__main__':
    main()
