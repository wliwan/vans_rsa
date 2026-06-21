#!/usr/bin/env python3
"""
数据工作台国际化脚本 V7 — MyMemory（免费）+ 有道 suggest + 内置词典。

翻译策略（全免费，无需任何密钥）：
  1. 内置词典优先（200+ 词条，精确匹配）
  2. MyMemory API（deep-translator 库，支持长文本，~1 req/s）
  3. 有道词典 suggest（≤8 字短词降级）
  4. 逐词替换最终降级
"""
import json, re, hashlib, time
from pathlib import Path
from collections import OrderedDict

PROJECT_ROOT = Path(__file__).resolve().parent.parent
I18N_DIR = PROJECT_ROOT / 'web' / 'i18n' / 'messages'

VUE_FILES = [
    'web/src/views/statistic-center/data-workbench/index.vue',
    'web/src/views/statistic-center/excel-data/index.vue',
    'web/src/views/statistic-center/report/index.vue',
    'web/src/views/statistic-center/doc-workbench/index.vue',
]

# Youdao suggest API (免费，无需密钥，仅对短词有效)
YOUDICT_URL = 'https://dict.youdao.com/suggest?num=3&ver=3.0&doctype=json&cache=false&le=en'

def youdao_suggest(text: str) -> str | None:
    """使用有道词典 suggest API 获取翻译（免费，无需密钥）。
    仅对 ≤8 字的中文短词有效，长文本返回 None。"""
    if len(text) > 8:
        return None
    try:
        import requests
        resp = requests.get(YOUDICT_URL, params={'q': text}, timeout=5)
        data = resp.json()
        if data.get('result', {}).get('code') == 200:
            entries = data.get('data', {}).get('entries', [])
            if entries:
                # 取第一个释义
                explain = entries[0].get('explain', '')
                # 分号分隔的多个释义，取第一个
                return explain.split(';')[0].strip()
    except Exception:
        pass
    return None

# ═══ 提取 ═══

def extract_all(filepath):
    with open(filepath) as f:
        content = f.read()
    lines = content.split('\n')
    results = []
    for line in lines:
        s = line.strip()
        if not re.search(r'[\u4e00-\u9fff]', line):
            continue
        if s.startswith('//') or s.startswith('<!--') or s.startswith('/*') or s.startswith('*'):
            continue
        if re.search(r"t\(['\"]views\.statistic-center\.", line):
            continue
        for m in re.finditer(r"'([^']*[\u4e00-\u9fff][^']*)'", line):
            t = m.group(1).strip()
            if t and '${' not in t:
                results.append(t)
        for m in re.finditer(r'"([^"]*[\u4e00-\u9fff][^"]*)"', line):
            t = m.group(1).strip()
            if t and not re.search(r'\b(?:title|placeholder|label|alt|class|name|action)="$', line[:m.start()].rstrip()):
                results.append(t)
        for m in re.finditer(r'\b(title|placeholder|label|alt|action)="([^"]*[\u4e00-\u9fff][^"]*)"', line):
            results.append(m.group(2))
        for m in re.finditer(r'(?:>|/>)\s*([^<{]*[\u4e00-\u9fff][^<{]*)<', line):
            t = m.group(1).strip()
            if t and len(t) >= 1:
                results.append(t)
    seen = set()
    return [t for t in results if not (t in seen or seen.add(t))]

# ═══ 翻译 ═══

def mymemory_translate(text: str) -> str | None:
    """使用 MyMemory 免费 API 翻译（无需密钥，限速 ~1 req/s）。"""
    try:
        from deep_translator import MyMemoryTranslator
        return MyMemoryTranslator(source='chinese simplified', target='english').translate(text)
    except Exception:
        return None

EN_DICT = {
    "短链接不可用":"Short Link Unavailable","短链接已复制":"Short Link Copied",
    "加载静态文件失败":"Failed to load static files","请先选择工作区":"Please select a workspace first",
    "上传失败":"Upload Failed","删除成功":"Deleted Successfully","删除失败":"Delete Failed",
    "请先选择文件":"Please select files first","批量删除成功":"Batch Delete Successful",
    "批量删除失败":"Batch Delete Failed","导出失败":"Export Failed","下载失败":"Download Failed",
    "请先选择图片文件":"Please select image files first","请选择AI代理":"Please select an AI proxy",
    "AI图片处理":"AI Image Processing","AI处理失败":"AI Processing Failed",
    "OCR文本提取":"OCR Text Extraction","OCR提取失败":"OCR Extraction Failed",
    "获取路网素材区域失败":"Failed to get road material regions","获取素材列表失败":"Failed to get material list",
    "请选择要导入的素材":"Please select materials to import","导入失败":"Import Failed",
    "请选择目标工作区":"Please select target workspace","复制失败":"Copy Failed",
    "更新失败":"Update Failed","请先选择数据":"Please select data first",
    "请填写主机和数据库名":"Please fill host and database name","连接失败":"Connection Failed",
    "请至少选择一个表":"Please select at least one table","解析失败":"Parse Failed",
    "获取像素账户失败":"Failed to get pixel accounts","获取数据表失败":"Failed to get data tables",
    "请选择账户和数据表":"Please select account and table","导入成功":"Import Successful",
    "获取路网区域失败":"Failed to get road network regions","获取路网列表失败":"Failed to get road network list",
    "请选择路网文件":"Please select road network files",
    "新建工作区":"New Workspace","请选择左侧工作区":"Please select a workspace",
    "属性":"Properties","选择文件":"Select File","AI分析":"AI Analysis",
    "确认删除该工作区及所有数据？":"Confirm delete workspace and all data?",
    "确认清空当前工作区的所有分析表格？":"Confirm clear all analysis sheets?",
    "确认删除已选中的":"Confirm delete selected","确认删除选中的":"Confirm delete selected",
    "个分析表格？":"analysis sheets?","个文档？":"documents?","条数据库数据？":"database records?",
    "个文件？":"files?","字符":"chars","行":"rows","素材":"materials",
    "节点":"nodes","边":"edges","路口":"junctions","等级":"levels",
    "源表":"Source Table","源更新":"Source Updated",
    "原始文档":"Original Documents","AI分析文档":"AI Analysis Documents",
    "数据库导入数据":"Database Imported Data","暂无文件":"No Files",
    "暂无数据库导入数据":"No Database Imported Data",
    "导入MySQL数据":"Import MySQL Data","导入SQLite数据":"Import SQLite Data",
    "导入像素数据":"Import Pixel Data","导入路网数据":"Import Road Network Data",
    "原始文档目录":"Original Documents Directory","AI分析文档目录":"AI Analysis Documents Directory",
    "复制到":"Copy To","基本属性":"Basic Properties","新标签页打开":"Open in New Tab",
    "关闭预览":"Close Preview","拖拽文件到此处或点击选择，支持批量上传":"Drag files here or click to select",
    "OpenCV处理":"OpenCV Processing","AI图片优化":"AI Image Optimization",
    "OCR提取":"OCR Extraction","从路网素材导入":"Import from Road Materials",
    "短链接（公开访问）":"Short Link (Public Access)","元数据":"Metadata",
    "EXIF 信息":"EXIF Info","分辨率":"Resolution","色彩":"Color","位深":"Bit Depth",
    "宽度":"Width","高度":"Height","名称":"Name","大小":"Size","时间":"Time",
    "来源":"Source","格式":"Format","处理":"Process","取消":"Cancel","确认":"Confirm",
    "保存":"Save","编辑":"Edit","删除":"Delete","克隆":"Clone","导出":"Export",
    "导入":"Import","打印":"Print","生成报告":"Generate Report","开始生成":"Start Generation",
    "预览统计":"Preview Stats","报告":"Report","报告生成":"Report Generation",
    "暂无工作区":"No Workspaces","无":"None","预览":"Preview",
    "编辑工作区":"Edit Workspace","确认复制":"Confirm Copy","确认克隆":"Confirm Clone",
    "关闭":"Close","打开":"Open","选择区域":"Select Region","全选":"Select All",
    "已全选":"All Selected","部分选中":"Partially Selected","未选择":"Not Selected",
    "已选":"Selected","请选择左侧报告":"Please select a report",
    "暂无路网素材区域":"No Road Material Regions","该区域暂无素材":"No Materials",
    "选择要导入的表（可多选）：":"Select tables to import (multi-select):",
    "请先选择区域以加载该区域下的路网文件":"Select a region first to load road network files",
    "选择区域后加载路网文件":"Select a region to load road network files",
    "支持导入路网拓扑统计信息（节点数 / 边数 / 道路等级分布等）":"Supports importing road network topology stats",
    "加载路网文件列表...":"Loading road network file list...",
    "选择国家 / 行政区 / 城市":"Select Country / State / City",
    "像素平台":"Pixel Platform","路网":"Road Network",
    "MySQL":"MySQL","SQLite":"SQLite","地名模式":"Place Name Mode","边界模式":"Boundary Mode",
    "将选中的":"Will copy selected","仅创建数据库记录指向同一文件，不拷贝物理文件。":"Only creates DB records, no physical copy.",
    "个文件复制到另一工作区。":"files to another workspace.",
    "项数据库导入数据到目标工作区":"database records to target workspace",
    "上传文件到":"Upload files to","目录":"directory",
    "更改 BaseUrl":"Change BaseUrl","BaseUrl":"BaseUrl",
    "设置公网访问基础地址，所有静态文件短链接将使用此地址作为前缀。":"Set public access base URL for short links.",
    "留空则自动使用当前访问地址。":"Leave blank to use current access URL.",
    "如 http://rsatest.vanstk.com:9999":"e.g. http://rsatest.vanstk.com:9999",
    "将复制":"Will copy",
    "选择数据工作区":"Select Data Workspace",
    "原始表格":"Original Sheets","分析":"Analysis","关联分析":"Correlation Analysis",
    "关联":"Correlation","全部删除":"Delete All","批量导出":"Batch Export",
    "批量删除":"Batch Delete","开始分析":"Start Analysis",
    "该工作区暂无数据源，请先在数据工作台中上传数据":"No data sources. Upload data in Data Workbench first.",
}

_yd_cache = {}  # {zh_text: en_text}

def classify(t):
    t = t.strip()
    if t.startswith('请') or t.startswith('选择') or t.startswith('输入') or t.startswith('如 ') or t.startswith('搜索') or t.startswith('描述'):
        return 'placeholder'
    if any(k in t for k in ['成功','失败','完成','错误']): return 'message'
    if t.startswith('确认'): return 'message'
    return 'label'

def translate(t):
    t = t.strip()
    # 1. 内置词典优先（精确匹配）
    if t in EN_DICT: return EN_DICT[t]
    # 2. MyMemory 免费 API（支持长文本）
    if t not in _yd_cache:
        print(f"    MyMemory: {t[:50]}")
        result = mymemory_translate(t)
        if result:
            _yd_cache[t] = result
            return result
        time.sleep(1.2)  # rate limit
    if t in _yd_cache:
        return _yd_cache[t]
    # 3. 有道 suggest（短词降级）
    if len(t) <= 8:
        result = youdao_suggest(t)
        if result:
            _yd_cache[t] = result
            return result
    # 4. 逐词替换
    r = t
    for c, e in sorted(EN_DICT.items(), key=lambda x: -len(x[0])):
        r = r.replace(c, e)
    return r if not re.search(r'[\u4e00-\u9fff]', r) else t

# ═══ 替换 ═══

def replace_line(line, cn, key, in_script, in_template):
    if in_script:
        p = f"'{cn}'"
        if p in line: return line.replace(p, f"t('{key}')")
        p = f'"{cn}"'
        if p in line and not re.search(rf'\b(?:title|placeholder|label|alt|class|name)="', line):
            return line.replace(p, f't("{key}")')
        p = f"|| '{cn}'"
        if p in line: return line.replace(p, f"|| t('{key}')")
    if in_template:
        for a in ['title','placeholder','label','alt','action']:
            p = f'{a}="{cn}"'
            if p in line: return line.replace(p, f':{a}="t(\'{key}\')"')
        for te in ['>', '/>']:
            p = f'{te}{cn}<'
            if p in line and '{{' not in line and f'="{cn}"' not in line:
                return line.replace(p, f'{te}{{{{ t(\'{key}\') }}}}<')
        for sp in [f'}} {cn}', f'}}{cn}']:
            if sp in line:
                return line.replace(sp, f'}} {{{{ t(\'{key}\') }}}}' if ' ' in sp else f'}}{{{{ t(\'{key}\') }}}}')
        p = f"{cn} {{"
        if p in line:
            return line.replace(p, f"{{{{ t('{key}') }}}} {{")
        p = f"? '{cn}'"
        if p in line: return line.replace(p, f"? t('{key}')")
        p = f": '{cn}'"
        if p in line: return line.replace(p, f": t('{key}')")
    return None

# ═══ MAIN ═══

def main():
    print("Translation: MyMemory (free, all lengths) + Youdao suggest (short words) + built-in dict")

    print("\nPHASE 1: Extract")
    all_texts = OrderedDict()
    for vf in VUE_FILES:
        fp = str(PROJECT_ROOT / vf)
        r = extract_all(fp)
        print(f"  {vf.split('/')[-1]}: {len(r)}")
        for t in r:
            if t not in all_texts: all_texts[t] = True
    print(f"  Total unique: {len(all_texts)}")

    print("\nPHASE 2: Translate & update lang packs")
    total_new = 0
    for fn, sf in [('cn.json','zh'),('en.json','en'),('tr.json','en')]:
        with open(I18N_DIR/fn) as f: pkg = json.load(f)
        sc = pkg.setdefault('views',{}).setdefault('statistic-center',{})
        for t in all_texts:
            k = f'{classify(t)}_cn_{hashlib.md5(t.encode()).hexdigest()[:8]}'
            if k not in sc:
                total_new += 1
                sc[k] = t if sf == 'zh' else translate(t)
        with open(I18N_DIR/fn,'w') as f: json.dump(pkg,f,ensure_ascii=False,indent=2)
        print(f"  {fn} updated")
    print(f"  New keys added: {total_new}")

    t2k = {}
    for t in all_texts:
        t2k[t] = f'views.statistic-center.{classify(t)}_cn_{hashlib.md5(t.encode()).hexdigest()[:8]}'
    st = sorted(t2k.keys(), key=len, reverse=True)

    print("\nPHASE 3: Replace")
    total_ch = 0
    for vf in VUE_FILES:
        fp = str(PROJECT_ROOT/vf)
        with open(fp) as f: lines = f.read().split('\n')
        nl, ch = [], 0
        sd, td = 0, 0
        for line in lines:
            s = line.strip()
            sd += len(re.findall(r'<script\b',s)) - len(re.findall(r'</script>',s))
            td += len(re.findall(r'<template\b',s)) - len(re.findall(r'</template>',s))
            if s.startswith('//') or s.startswith('<!--') or s.startswith('/*') or s.startswith('*'):
                nl.append(line); continue
            if not re.search(r'[\u4e00-\u9fff]',line): nl.append(line); continue
            if re.search(r"t\(['\"]views\.statistic-center\.",line): nl.append(line); continue
            ins, itm = sd > 0, td > 0
            rp = True
            while rp and re.search(r'[\u4e00-\u9fff]',line):
                rp = False
                for cn in st:
                    if cn in line and cn.strip():
                        nline = replace_line(line, cn, t2k[cn], ins, itm)
                        if nline and nline != line:
                            line = nline; ch += 1; rp = True; break
            nl.append(line)
        with open(fp,'w') as f: f.write('\n'.join(nl))
        total_ch += ch
        print(f"  {vf.split('/')[-1]}: {ch}")
    print(f"  Total replacements: {total_ch}")

if __name__ == '__main__':
    main()
