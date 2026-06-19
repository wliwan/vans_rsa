#!/usr/bin/env python3
"""
i18n 国际化辅助脚本 — 帮助开发者快速将 Vue SFC 硬编码中文文本提取到语言包中。

用法:
  python scripts/i18n_helper.py scan <files...>         扫描硬编码中文，输出报告
  python scripts/i18n_helper.py extract <module> <file> 提取中文，生成 key 映射 JSON
  python scripts/i18n_helper.py apply <mapping.json>    将映射写入三个语言包
  python scripts/i18n_helper.py check <file>            验证组件的 t() 引用在语言包中都有定义
  python scripts/i18n_helper.py translate <mapping.json> 调用 MyMemory API 翻译中→英/土
  python scripts/i18n_helper.py translate <map.json> --backend google  使用 Google 后端
  python scripts/i18n_helper.py translate <map.json> --backend dictionary  离线词典快速翻译
  python scripts/i18n_helper.py validate                检查所有语言包 JSON 合法性

示例:
  python scripts/i18n_helper.py scan web/src/views/network/my-module/index.vue
  python scripts/i18n_helper.py extract myModule web/src/views/network/my-module/index.vue
  python scripts/i18n_helper.py translate /tmp/i18n_mapping.json
  python scripts/i18n_helper.py apply /tmp/i18n_mapping.json
  python scripts/i18n_helper.py check web/src/views/network/road-network-workbench/index.vue
"""

import argparse
import json
import os
import re
import sys
from collections import OrderedDict
from pathlib import Path

# ── 路径配置 ──
PROJECT_ROOT = Path(__file__).resolve().parent.parent
I18N_DIR = PROJECT_ROOT / "web" / "i18n" / "messages"
CN_FILE = I18N_DIR / "cn.json"
EN_FILE = I18N_DIR / "en.json"
TR_FILE = I18N_DIR / "tr.json"
INDEX_FILE = I18N_DIR / "index.js"

# ── 常见中文 ↔ 英文 ↔ 土耳其语翻译词典 ──
# 新增模块时，脚本优先查此词典；未命中则用拼音生成 key
TRANSLATION_DICT = {
    # 通用
    "管理": ("Management", "Yönetimi"),
    "文件": ("File", "Dosya"),
    "下载": ("Download", "İndir"),
    "上传": ("Upload", "Yükle"),
    "编辑": ("Edit", "Düzenle"),
    "删除": ("Delete", "Sil"),
    "保存": ("Save", "Kaydet"),
    "取消": ("Cancel", "İptal"),
    "确认": ("Confirm", "Onayla"),
    "搜索": ("Search", "Ara"),
    "查询": ("Query", "Sorgula"),
    "导出": ("Export", "Dışa Aktar"),
    "导入": ("Import", "İçe Aktar"),
    "新建": ("New", "Yeni"),
    "清除": ("Clear", "Temizle"),
    "成功": ("Success", "Başarılı"),
    "失败": ("Failed", "Başarısız"),
    "名称": ("Name", "İsim"),
    "代码": ("Code", "Kod"),
    "类型": ("Type", "Tür"),
    "状态": ("Status", "Durum"),
    "大小": ("Size", "Boyut"),
    "时间": ("Time", "Zaman"),
    "操作": ("Actions", "İşlemler"),
    "格式": ("Format", "Format"),
    "节点": ("Node", "Düğüm"),
    "边": ("Edge", "Kenar"),
    "模式": ("Mode", "Mod"),
    "标题": ("Title", "Başlık"),
    "描述": ("Description", "Açıklama"),
    "详情": ("Detail", "Detay"),
    "统计": ("Statistics", "İstatistik"),
    "参数": ("Parameters", "Parametreler"),
    "字段": ("Field", "Alan"),
    "模板": ("Template", "Şablon"),
    "代理": ("Proxy", "Proxy"),
    "配置": ("Configuration", "Yapılandırma"),
    "设置": ("Settings", "Ayarlar"),
    "选择": ("Select", "Seç"),
    "筛选": ("Filter", "Filtre"),
    "分段": ("Segment", "Segment"),
    "长度": ("Length", "Uzunluk"),
    "处理": ("Process", "İşle"),
    "执行": ("Execute", "Çalıştır"),
    "国家": ("Country", "Ülke"),
    "行政区": ("State", "Eyalet/Bölge"),
    "城市": ("City", "Şehir"),
    "区域": ("Region", "Bölge"),
    "边界": ("Boundary", "Sınır"),
    "路网": ("Road Network", "Yol Ağı"),
    "工作台": ("Workbench", "Çalışma Masası"),
    "图层": ("Layer", "Katman"),
    "底图": ("Basemap", "Altlık Harita"),
    "图例": ("Legend", "Gösterge"),
    "坐标": ("Coordinates", "Koordinatlar"),
    "全屏": ("Fullscreen", "Tam Ekran"),
    "缩放": ("Zoom", "Yakınlaştırma"),
    "中心": ("Center", "Merkez"),
    "纬度": ("Latitude", "Enlem"),
    "经度": ("Longitude", "Boylam"),
    "时区": ("Timezone", "Saat Dilimi"),
    "人口": ("Population", "Nüfus"),
    "面积": ("Area", "Alan"),
    "首都": ("Capital", "Başkent"),
    "首府": ("Capital", "Başkent"),
    "本地": ("Local", "Yerel"),
    "密度": ("Density", "Yoğunluk"),
    "里程": ("Length", "Uzunluk"),
    "路口": ("Junction", "Kavşak"),
    "等级": ("Level", "Seviye"),
    "缓存": ("Cache", "Önbellek"),
    "瓦片": ("Tile", "Döşeme"),
    "数据集": ("Dataset", "Veri Kümesi"),
    "地图": ("Map", "Harita"),
    "卫星": ("Satellite", "Uydu"),
    # 按钮/动作
    "加载中": ("Loading", "Yükleniyor"),
    "暂无数据": ("No Data", "Veri Yok"),
    "有子级": ("Has Children", "Alt Öğeler Var"),
    "请选择": ("Please Select", "Lütfen Seçin"),
    "请输入": ("Please Enter", "Lütfen Girin"),
    "请先": ("Please First", "Lütfen Önce"),
    "未下载": ("Not Downloaded", "İndirilmedi"),
    "已下载": ("Downloaded", "İndirildi"),
    "下载中": ("Downloading", "İndiriliyor"),
    "待下载": ("Pending", "Bekliyor"),
    "检测中": ("Checking", "Kontrol Ediliyor"),
}


def _to_snake(name: str) -> str:
    """将中文文本转为 snake_case key。优先取最后2-3个中文词。"""
    # 提取中文词
    chinese = re.findall(r'[\u4e00-\u9fff]+', name)
    if not chinese:
        # fallback: 拼音首字母
        return re.sub(r'[^a-zA-Z0-9]', '_', name).strip('_').lower()[:30]
    # 取最后2个有意义的词
    key_words = [w for w in chinese if len(w) >= 1][-3:]
    # 查翻译词典转英文
    parts = []
    for w in key_words:
        if w in TRANSLATION_DICT:
            en = TRANSLATION_DICT[w][0].lower().replace(' ', '_').replace('/', '_')
            parts.append(en)
        else:
            parts.append(w)
    result = '_'.join(parts)
    # 清理特殊字符
    result = re.sub(r'[^a-zA-Z0-9_\u4e00-\u9fff]', '_', result)
    # 如果还有中文，用简单映射
    if re.search(r'[\u4e00-\u9fff]', result):
        result = 'key_' + str(hash(name) % 10000)
    return result.lower()[:40]


# ── 翻译 API 客户端 ──
_translation_cache: dict[str, dict[str, str]] = {}  # {text: {en: ..., tr: ...}}
_translate_backend = "mymemory"  # mymemory | google
_translate_rate_limit = 1.2  # 每秒请求数（MyMemory 免费版限制）

# MyMemory 使用语言全名（非 ISO 代码）
_MYMEMORY_LANG = {
    "zh-CN": "chinese simplified",
    "en": "english",
    "tr": "turkish",
}


def _api_translate(text: str, source: str, target: str, backend: str = "mymemory") -> str:
    """调用翻译 API 翻译单条文本。"""
    import time
    text = text.strip()
    if not text:
        return text

    # 纯数字/符号不翻译
    if re.match(r'^[\d\s\.\,\-\+\%\/\(\)\[\]\{\}]+$', text):
        return text

    # 缓存命中
    cache_key = f"{text}|{source}|{target}"
    if cache_key in _translation_cache:
        return _translation_cache[cache_key]

    try:
        if backend == "google":
            from deep_translator import GoogleTranslator
            result = GoogleTranslator(source=source, target=target).translate(text)
        elif backend == "mymemory":
            from deep_translator import MyMemoryTranslator
            src = _MYMEMORY_LANG.get(source, source)
            tgt = _MYMEMORY_LANG.get(target, target)
            result = MyMemoryTranslator(source=src, target=tgt).translate(text)
        else:
            raise ValueError(f"Unknown backend: {backend}")
    except Exception as e:
        # 降级到词典翻译
        print(f"  ⚠ API 翻译失败 ({source}→{target}): {e}，降级到词典")
        time.sleep(0.5)
        return _dict_translate(text, source, target)

    _translation_cache[cache_key] = result
    time.sleep(_translate_rate_limit)  # 限流
    return result


def _dict_translate(text: str, source: str, target: str) -> str:
    """用内置词典翻译（降级方案）。"""
    result = text
    for cn, (en, tr) in sorted(TRANSLATION_DICT.items(), key=lambda x: -len(x[0])):
        if target == "en":
            result = result.replace(cn, en)
        elif target == "tr":
            result = result.replace(cn, tr)
    return result


def _translate_cn_to_en(text: str) -> str:
    """翻译中文→英文（API + 词典降级）。"""
    if _translate_backend == "dictionary":
        return _dict_translate(text, "zh", "en")
    return _api_translate(text, "zh-CN", "en", _translate_backend)


def _translate_cn_to_tr(text: str) -> str:
    """翻译中文→土耳其语（先转英文再转土耳其语，MyMemory 不支持直译）。"""
    if _translate_backend == "dictionary":
        return _dict_translate(text, "zh", "tr")
    # 两步翻译: zh-CN → en → tr
    en = _translate_cn_to_en(text)
    if re.search(r'[\u4e00-\u9fff]', en):
        # 英文翻译失败（残留中文），降级到词典
        return _dict_translate(text, "zh", "tr")
    return _api_translate(en, "en", "tr", _translate_backend)


# ────────────────────────────────────────────
# 扫描：提取硬编码中文
# ────────────────────────────────────────────

def extract_chinese_from_vue(filepath: str) -> list[dict]:
    """从 Vue SFC 中提取所有未国际化的硬编码中文文本。"""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    lines = content.split('\n')

    results = []
    # 找到 template 和 script 区域
    in_template = False
    in_script = False

    for i, line in enumerate(lines, 1):
        stripped = line.strip()

        # 跟踪区域
        if '<template>' in stripped:
            in_template = True
            in_script = False
            continue
        if '</template>' in stripped:
            in_template = False
            continue
        if '<script' in stripped:
            in_script = True
            in_template = False
            continue
        if '</script>' in stripped:
            in_script = False
            continue

        if not (in_template or in_script):
            continue

        # 跳过纯注释行
        if stripped.startswith('//') or stripped.startswith('<!--') or stripped.startswith('*'):
            continue

        # 跳过 import / defineOptions / console
        if re.match(r'^(import|defineOptions|console\.)', stripped):
            # defineOptions name 保留不翻译
            if 'defineOptions' in stripped:
                continue
            if 'import' in stripped:
                continue

        # 提取中文字符串（单引号和双引号，模板插值）
        # 匹配 '...中文...' 或 "..." 或 >...中文...< 或 {{ ...中文... }}
        patterns = [
            (r"'([^']*[\u4e00-\u9fff][^']*)'", 1),
            (r'"([^"]*[\u4e00-\u9fff][^"]*)"', 1),
            (r'>([^<]*[\u4e00-\u9fff][^<]*)<', 1),
            (r'\{\{\s*([^}]*[\u4e00-\u9fff][^}]*)\s*\}\}', 1),
        ]

        for pattern, group in patterns:
            for m in re.finditer(pattern, line):
                text = m.group(group).strip()
                if not text or len(text) < 1:
                    continue
                # 过滤掉已使用 t() 的
                if re.search(r'\bt\(', text) or re.search(r'\$t\(', text):
                    continue
                # 过滤纯变量/表达式
                if re.match(r'^[\w\s\.\(\)\+\-\*/\?:!<>=&|,\[\]\{\}$`]+$', text) and not re.search(r'[\u4e00-\u9fff]', text):
                    continue
                # 过滤 defineOptions name
                if "defineOptions" in text:
                    continue
                # 必须有中文
                if not re.search(r'[\u4e00-\u9fff]', text):
                    continue

                # 清理文本
                clean = text.strip()
                # 去掉模板语法残余
                clean = re.sub(r'^[\s\'"]+|[\s\'"]+$', '', clean)

                if clean and re.search(r'[\u4e00-\u9fff]', clean):
                    results.append({
                        'line': i,
                        'text': clean,
                        'context': stripped[:80],
                        'key': _to_snake(clean),
                    })

    # 去重（按 text）
    seen = set()
    unique = []
    for r in results:
        if r['text'] not in seen:
            seen.add(r['text'])
            unique.append(r)
    return unique


def scan_files(files: list[str]):
    """扫描多个文件，输出硬编码中文报告。"""
    all_results = []
    for f in files:
        if not os.path.exists(f):
            print(f"  ⚠ 文件不存在: {f}")
            continue
        results = extract_chinese_from_vue(f)
        if results:
            print(f"\n📄 {f} ({len(results)} 处硬编码中文)")
            for r in results:
                print(f"  L{r['line']:4d}  →  {r['key']:30s}  «{r['text'][:50]}»")
            all_results.extend(results)
        else:
            print(f"  ✅ {f} — 已完全国际化")

    print(f"\n📊 总计: {len(all_results)} 处硬编码中文（已去重）")
    return all_results


# ────────────────────────────────────────────
# 提取：生成 key 映射 JSON
# ────────────────────────────────────────────

def extract_to_mapping(module_name: str, filepath: str, output_path: str | None = None):
    """提取硬编码中文，生成 key→中文 映射 JSON 文件。"""
    results = extract_chinese_from_vue(filepath)
    if not results:
        print("✅ 未发现硬编码中文")
        return

    mapping = OrderedDict()
    for r in results:
        # 用 module.key 格式
        full_key = f"views.{module_name}.{r['key']}"
        # 如果 key 重复，追加序号
        base = full_key
        n = 1
        while full_key in mapping:
            full_key = f"{base}_{n}"
            n += 1
        mapping[full_key] = {
            'zh': r['text'],
            'source_line': r['line'],
            'context': r['context'],
        }

    if output_path:
        output_path = output_path
    else:
        output_path = f"/tmp/i18n_mapping_{module_name}.json"

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(mapping, f, ensure_ascii=False, indent=2)

    print(f"✅ 已生成 {len(mapping)} 条映射 → {output_path}")
    print(f"   下一步: python scripts/i18n_helper.py translate {output_path}")
    return output_path


# ────────────────────────────────────────────
# 翻译：填充 en/tr 字段
# ────────────────────────────────────────────

def translate_mapping(mapping_path: str, backend: str = "mymemory"):
    """读取映射 JSON，通过翻译 API 自动填充英文和土耳其语翻译。"""
    global _translate_backend
    _translate_backend = backend

    with open(mapping_path, 'r', encoding='utf-8') as f:
        mapping = json.load(f)

    total = len(mapping)
    print(f"🔄 翻译 {total} 条文本 (后端: {backend})...")

    for i, (key, val) in enumerate(mapping.items(), 1):
        zh = val['zh']
        if 'en' not in val or not val.get('en'):
            val['en'] = _translate_cn_to_en(zh)
            print(f"  [{i}/{total}] zh→en: {zh[:40]} → {val['en'][:40]}")
        if 'tr' not in val or not val.get('tr'):
            val['tr'] = _translate_cn_to_tr(zh)
            print(f"  [{i}/{total}] zh→tr: {zh[:40]} → {val['tr'][:40]}")

    with open(mapping_path, 'w', encoding='utf-8') as f:
        json.dump(mapping, f, ensure_ascii=False, indent=2)

    untranslated_en = sum(1 for v in mapping.values() if re.search(r'[\u4e00-\u9fff]', v.get('en', '')))
    untranslated_tr = sum(1 for v in mapping.values() if re.search(r'[\u4e00-\u9fff]', v.get('tr', '')))

    print(f"\n✅ 已填充翻译 → {mapping_path}")
    print(f"   英文未翻译残留: {untranslated_en} 条")
    print(f"   土耳其语未翻译残留: {untranslated_tr} 条")
    if untranslated_en or untranslated_tr:
        print(f"   请手动编辑 JSON 中残留中文的 en/tr 字段")
    return mapping_path


# ────────────────────────────────────────────
# 应用：将映射写入三个语言包
# ────────────────────────────────────────────

def _deep_set(d: dict, key_path: str, value):
    """按点分隔路径设置嵌套字典值。"""
    parts = key_path.split('.')
    for part in parts[:-1]:
        if part not in d:
            d[part] = {}
        d = d[part]
    d[parts[-1]] = value


def _load_json_safe(filepath: Path) -> dict:
    """安全加载 JSON 文件。"""
    if filepath.exists():
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}


def apply_mapping(mapping_path: str):
    """将映射文件中的 key-value 写入三个语言包。"""
    with open(mapping_path, 'r', encoding='utf-8') as f:
        mapping = json.load(f)

    cn = _load_json_safe(CN_FILE)
    en = _load_json_safe(EN_FILE)
    tr = _load_json_safe(TR_FILE)

    added = 0
    for key, val in mapping.items():
        # 检查是否已存在
        parts = key.split('.')
        tmp = cn
        exists = True
        for p in parts:
            if isinstance(tmp, dict) and p in tmp:
                tmp = tmp[p]
            else:
                exists = False
                break
        if exists:
            continue

        _deep_set(cn, key, val['zh'])
        _deep_set(en, key, val.get('en', val['zh']))
        _deep_set(tr, key, val.get('tr', val['zh']))
        added += 1

    # 写回文件
    for filepath, data in [(CN_FILE, cn), (EN_FILE, en), (TR_FILE, tr)]:
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"✅ 已写入 {added} 条新 key → cn.json / en.json / tr.json")
    if added < len(mapping):
        skipped = len(mapping) - added
        print(f"   ⏭  跳过 {skipped} 条（已存在）")


# ────────────────────────────────────────────
# 检查：验证组件 t() 引用
# ────────────────────────────────────────────

def check_vue_i18n(filepath: str):
    """检查 Vue 文件中所有 t() 引用是否在语言包中有定义。"""
    cn = _load_json_safe(CN_FILE)

    def flatten(obj, prefix=''):
        keys = set()
        if isinstance(obj, dict):
            for k, v in obj.items():
                full = f"{prefix}.{k}" if prefix else k
                if isinstance(v, (dict, list)):
                    keys.update(flatten(v, full))
                else:
                    keys.add(full)
        return keys

    json_keys = flatten(cn)

    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # 提取所有 t('...') 和 _t('...') 引用（只匹配包含点号的 i18n key）
    raw_pattern = re.findall(r"(?:_t|t)\(['\"]([^'\"]+)['\"]", content)
    component_keys = {k for k in raw_pattern if '.' in k and len(k) > 3}

    missing = component_keys - json_keys
    extra = json_keys - component_keys

    print(f"📊 组件引用: {len(component_keys)} | JSON 定义: {len(json_keys)}")
    if missing:
        print(f"\n❌ 缺失 key ({len(missing)}):")
        for k in sorted(missing):
            print(f"  - {k}")
    else:
        print("\n✅ 所有 key 已在语言包中定义")

    if extra:
        # 只显示与组件同模块前缀下的额外 key
        prefixes = set()
        for k in component_keys:
            parts = k.split('.')
            if len(parts) >= 2:
                prefixes.add('.'.join(parts[:2]))
        related_extra = {k for k in extra if any(k.startswith(p) for p in prefixes)}
        if related_extra:
            print(f"\nℹ️  语言包中同模块下未直接引用的 key ({len(related_extra)}):")
            for k in sorted(related_extra):
                print(f"  - {k}")

    return len(missing) == 0


# ────────────────────────────────────────────
# 添加语言
# ────────────────────────────────────────────

def add_locale(locale_code: str):
    """从 cn.json 复制结构，创建新语言模板。"""
    target = I18N_DIR / f"{locale_code}.json"
    if target.exists():
        print(f"⚠ {target} 已存在")
        return

    cn = _load_json_safe(CN_FILE)

    def empty_values(obj):
        if isinstance(obj, dict):
            return {k: empty_values(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [empty_values(v) for v in obj]
        if isinstance(obj, str) and re.search(r'[\u4e00-\u9fff]', obj):
            return f"[{obj}]"  # 标记待翻译
        return obj

    template = empty_values(cn)
    # 更新 lang 字段
    if 'lang' in template:
        template['lang'] = f"[Language: {locale_code}]"

    with open(target, 'w', encoding='utf-8') as f:
        json.dump(template, f, ensure_ascii=False, indent=2)

    # 更新 index.js
    if INDEX_FILE.exists():
        with open(INDEX_FILE, 'r', encoding='utf-8') as f:
            content = f.read()

        import_line = f"import * as {locale_code} from './{locale_code}.json'"
        if import_line not in content:
            # 找到最后一个 import 后插入
            content = re.sub(
                r"(import \* as \w+ from '\./[^']+\.json'\n)(?!import)",
                rf"\1{import_line}\n",
                content,
                count=1,
            )

        # 在 export default 中添加
        if f"  {locale_code}," not in content:
            content = re.sub(
                r"(export default \{\n)((?:\s+\w+,\n)+)",
                rf"\1\2  {locale_code},\n",
                content,
            )

        with open(INDEX_FILE, 'w', encoding='utf-8') as f:
            f.write(content)

    print(f"✅ 已创建 {target}，并更新 index.js")
    print(f"   请手动翻译所有 [...] 标记的文本")


# ────────────────────────────────────────────
# 验证所有语言包
# ────────────────────────────────────────────

def validate_all():
    """检查所有 JSON 语言包的合法性。"""
    errors = []
    for f in [CN_FILE, EN_FILE, TR_FILE]:
        if not f.exists():
            errors.append(f"⚠ {f.name} 不存在")
            continue
        try:
            with open(f, 'r', encoding='utf-8') as fp:
                json.load(fp)
        except json.JSONDecodeError as e:
            errors.append(f"❌ {f.name}: {e}")

    if errors:
        print('\n'.join(errors))
        return False
    else:
        # 检查 key 一致性
        cn = _load_json_safe(CN_FILE)
        en = _load_json_safe(EN_FILE)
        tr = _load_json_safe(TR_FILE)

        def all_keys(obj, prefix=''):
            keys = set()
            if isinstance(obj, dict):
                for k, v in obj.items():
                    full = f"{prefix}.{k}" if prefix else k
                    if isinstance(v, (dict, list)):
                        keys.update(all_keys(v, full))
                    else:
                        keys.add(full)
            return keys

        cn_keys = all_keys(cn)
        en_keys = all_keys(en)
        tr_keys = all_keys(tr)

        cn_only = cn_keys - en_keys
        en_only = en_keys - cn_keys
        tr_only = tr_keys - cn_keys

        if cn_only or en_only or tr_only:
            if cn_only:
                print(f"⚠ cn.json 独有 {len(cn_only)} key（en/tr 缺失）")
            if en_only:
                print(f"⚠ en.json 独有 {len(en_only)} key（cn 缺失）")
            if tr_only:
                print(f"⚠ tr.json 独有 {len(tr_only)} key（cn 缺失）")
        else:
            print(f"✅ 三个语言包 key 完全一致（{len(cn_keys)} 条）")
        return True


# ────────────────────────────────────────────
# CLI
# ────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="i18n 国际化辅助脚本",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    sub = parser.add_subparsers(dest='command', help='子命令')

    p_scan = sub.add_parser('scan', help='扫描硬编码中文')
    p_scan.add_argument('files', nargs='+', help='Vue 文件路径')

    p_extract = sub.add_parser('extract', help='提取中文生成 key 映射')
    p_extract.add_argument('module', help='模块名（如 myModule）')
    p_extract.add_argument('file', help='Vue 文件路径')
    p_extract.add_argument('-o', '--output', help='输出 JSON 文件路径')

    p_translate = sub.add_parser('translate', help='调用开源翻译 API 翻译')
    p_translate.add_argument('mapping', help='映射 JSON 文件路径')
    p_translate.add_argument('--backend', choices=['mymemory', 'google', 'dictionary'],
                             default='mymemory',
                             help='翻译后端: mymemory(免费/默认), google, dictionary(离线词典)')

    p_apply = sub.add_parser('apply', help='将映射写入语言包')
    p_apply.add_argument('mapping', help='映射 JSON 文件路径')

    p_check = sub.add_parser('check', help='验证组件 i18n 引用')
    p_check.add_argument('file', help='Vue 文件路径')

    p_add = sub.add_parser('add-locale', help='添加新语言')
    p_add.add_argument('locale', help='locale 代码（如 fr, ja）')

    p_val = sub.add_parser('validate', help='验证所有语言包')

    args = parser.parse_args()

    if args.command == 'scan':
        scan_files(args.files)
    elif args.command == 'extract':
        extract_to_mapping(args.module, args.file, args.output)
    elif args.command == 'translate':
        translate_mapping(args.mapping, backend=args.backend)
    elif args.command == 'apply':
        apply_mapping(args.mapping)
    elif args.command == 'check':
        ok = check_vue_i18n(args.file)
        sys.exit(0 if ok else 1)
    elif args.command == 'add-locale':
        add_locale(args.locale)
    elif args.command == 'validate':
        ok = validate_all()
        sys.exit(0 if ok else 1)
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
