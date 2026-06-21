#!/usr/bin/env python3
"""补充翻译并更新 en.json / tr.json"""
import json
import re
import hashlib

with open('scripts/i18n_data_workbench_mapping.json', 'r') as f:
    data = json.load(f)

all_keys = data['all_keys']

EN_DICT = {
    "AI分析": "AI Analysis",
    "AI 代理": "AI Proxy",
    "静态文件": "Static Files",
    "数据源": "Data Source",
    "像素平台": "Pixel Platform",
    "路网": "Road Network",
    "AI图片优化": "AI Image Optimization",
    "文件": "File",
    "格式": "Format",
    "操作类型": "Operation Type",
    "高度 (px, 0=等比)": "Height (px, 0=proportional)",
    "角度 (度)": "Angle (deg)",
    "缩放": "Zoom",
    "X 起点": "X Start",
    "Y 起点": "Y Start",
    "垂直翻转 (0)": "Flip Vertical (0)",
    "水平翻转 (1)": "Flip Horizontal (1)",
    "两者 (-1)": "Both (-1)",
    "翻转方向": "Flip Direction",
    "上": "Top",
    "下": "Bottom",
    "左": "Left",
    "右": "Right",
    "颜色 (Hex)": "Color (Hex)",
    "亮度 (0=暗, 1=原图, >1=亮)": "Brightness (0=dark, 1=original, >1=bright)",
    "对比度 (0=灰, 1=原图, >1=高对比)": "Contrast (0=gray, 1=original, >1=high)",
    "灰度(GRAY)": "Grayscale (GRAY)",
    "目标色彩空间": "Target Color Space",
    "高斯(gaussian)": "Gaussian",
    "中值(median)": "Median",
    "双边(bilateral)": "Bilateral",
    "模糊类型": "Blur Type",
    "核大小 (奇数)": "Kernel Size (odd)",
    "腐蚀(erode)": "Erode",
    "膨胀(dilate)": "Dilate",
    "开(open)": "Open",
    "闭(close)": "Close",
    "操作": "Operation",
    "核大小": "Kernel Size",
    "迭代次数": "Iterations",
    "非局部均值(nlmeans)": "Non-local Means (nlmeans)",
    "方法": "Method",
    "滤波强度 (h)": "Filter Strength (h)",
    "全局(global)": "Global",
    "裁剪限制": "Clip Limit",
    "网格大小": "Grid Size",
    "阈值(threshold)": "Threshold",
    "边距": "Margin",
    "Skill（可选）": "Skill (optional)",
    "提示词": "Prompt",
    "AI 优化": "AI Optimize",
    "数据库名称": "Database Name",
    "重新连接": "Reconnect",
    "上传 SQLite 文件": "Upload SQLite File",
    "数据表": "Data Table",
    "选择数据表": "Select Data Table",
    "下载": "Download",
    "确认删除该工作区及所有数据？": "Confirm delete this workspace and all its data?",
    "确认清空当前工作区的所有分析表格？": "Confirm clear all analysis sheets in this workspace?",
    "确认清空当前工作区的所有AI分析文档？": "Confirm clear all AI analysis documents in this workspace?",
    "编辑文档 - ": "Edit Document - ",
    "编辑工作区": "Edit Workspace",
    "导出${type}失败": "Failed to export ${type}",
    "开始生成": "Start Generation",
    "处理": "Process",
    "原始表格目录": "Original Sheets Directory",
    "AI分析文档目录": "AI Analysis Documents Directory",
    "选择AI代理": "Select AI Proxy",
    "选择原始表格": "Select Original Sheet",
    "选择分析表格": "Select Analysis Sheet",
    "输入处理提示词，或选择 Skill 自动填充": "Enter processing prompt, or select Skill to auto-fill",
    "描述你想要的图片处理效果，如：提升画质、增强色彩、去雾...": "Describe desired image processing effect, e.g.: enhance quality, boost colors, dehaze...",
    "选择国家 / 行政区 / 城市": "Select Country / State / City",
    "搜索并选择有路网数据的区域…": "Search and select regions with road network data…",
    "全部区域": "All Regions",
    "选择区域后加载路网文件": "Select a region to load road network files",
    "支持导入路网拓扑统计信息（节点数 / 边数 / 道路等级分布等）": "Supports importing road network topology stats (nodes / edges / road class distribution etc.)",
    "编辑": "Edit",
    "删除": "Delete",
    "保存": "Save",
    "取消": "Cancel",
    "确认": "Confirm",
    "导出": "Export",
    "导入": "Import",
    "新建": "New",
    "清空": "Clear",
    "复制": "Copy",
    "克隆": "Clone",
    "预览": "Preview",
    "查看": "View",
    "搜索": "Search",
    "上传": "Upload",
    "关闭预览": "Close Preview",
    "新标签页打开": "Open in New Tab",
    "复制短链接": "Copy Short Link",
    "加载中...": "Loading...",
    "暂无数据": "No Data",
    "暂无": "None",
    "关闭": "Close",
    "共": "Total",
    "条": "items",
    "已选": "Selected",
    "未选择": "Not Selected",
    "已全选": "All Selected",
    "部分选中": "Partially Selected",
    "项": "items",
    "处理中": "Processing",
    "基本属性": "Basic Properties",
    "短链接（公开访问）": "Short Link (Public Access)",
    "短链接不可用": "Short Link Unavailable",
    "短链接已复制": "Short Link Copied",
    "EXIF 信息": "EXIF Info",
    "分辨率": "Resolution",
    "色彩": "Color",
    "位深": "Bit Depth",
    "宽度": "Width",
    "高度": "Height",
    "原始表格": "Original Sheets",
    "拆解分析表格": "Analysis Sheets",
    "分析名称": "Analysis Name",
    "关联分析": "Correlation Analysis",
    "分析": "Analysis",
    "暂无原始表格": "No Original Sheets",
    "暂无分析结果": "No Analysis Results",
    "暂无文档": "No Documents",
    "暂无文件": "No Files",
    "暂无工作区": "No Workspaces",
    "暂无分析文档": "No Analysis Documents",
    "开始分析": "Start Analysis",
    "目标工作区": "Target Workspace",
    "复制到": "Copy To",
    "全选": "Select All",
    "全部删除": "Delete All",
    "确认克隆": "Clone",
    "报告生成": "Report Generation",
    "生成报告": "Generate Report",
    "生成文书": "Generate Document",
    "数据工作台": "Data Workbench",
    "报告": "Report",
    "工作区": "Workspace",
    "新建工作区": "New Workspace",
    "数据库导入数据": "Database Imported Data",
    "MySQL": "MySQL",
    "SQLite": "SQLite",
    "导入MySQL数据": "Import MySQL Data",
    "导入SQLite数据": "Import SQLite Data",
    "导入像素数据": "Import Pixel Data",
    "导入路网数据": "Import Road Network Data",
    "暂无数据库导入数据": "No Database Imported Data",
    "点击上方按钮导入 MySQL / SQLite / 像素平台 / 路网数据": "Click above buttons to import MySQL / SQLite / Pixel / Road Network data",
    "原始文档": "Original Documents",
    "AI分析文档": "AI Analysis Documents",
    "拖拽文件到此处或点击选择，支持批量上传": "Drag files here or click to select, batch upload supported",
    "OpenCV处理": "OpenCV Processing",
    "OCR提取": "OCR Extraction",
    "从路网素材导入": "Import from Road Materials",
    "主机地址": "Host Address",
    "端口": "Port",
    "用户名": "Username",
    "密码": "Password",
    "数据库名": "Database Name",
    "文件名称": "File Name",
    "像素账户": "Pixel Account",
    "创建成功": "Created Successfully",
    "更新失败": "Update Failed",
    "生成失败": "Generation Failed",
    "连接失败": "Connection Failed",
    "连接成功": "Connection Successful",
    "导入成功": "Import Successful",
    "导入失败": "Import Failed",
    "上传失败": "Upload Failed",
    "删除成功": "Delete Successful",
    "删除失败": "Delete Failed",
    "批量删除成功": "Batch Delete Successful",
    "批量删除失败": "Batch Delete Failed",
    "导出失败": "Export Failed",
    "下载失败": "Download Failed",
    "复制失败": "Copy Failed",
    "克隆失败": "Clone Failed",
    "解析失败": "Parse Failed",
    "AI处理失败": "AI Processing Failed",
    "AI处理完成": "AI Processing Completed",
    "OpenCV处理失败": "OpenCV Processing Failed",
    "OpenCV处理完成": "OpenCV Processing Completed",
    "OCR提取失败": "OCR Extraction Failed",
    "OCR提取完成": "OCR Extraction Completed",
    "关联分析完成": "Correlation Analysis Completed",
    "请先选择工作区": "Please select a workspace first",
    "请先选择文件": "Please select files first",
    "请先选择数据": "Please select data first",
    "请先选择图片文件": "Please select image files first",
    "请选择AI代理": "Please select an AI proxy",
    "请选择目标工作区": "Please select target workspace",
    "请选择要导入的素材": "Please select materials to import",
    "请至少选择一个表": "Please select at least one table",
    "请选择账户和数据表": "Please select account and table",
    "请选择路网文件": "Please select road network files",
    "请先选择原始表格": "Please select original sheets first",
    "请先选择原始文档": "Please select original documents first",
    "请先选择分析文档": "Please select analysis documents first",
    "请至少选择一个数据源": "Please select at least one data source",
    "请至少选择一项数据": "Please select at least one item",
    "获取路网区域失败": "Failed to get road network regions",
    "获取路网列表失败": "Failed to get road network list",
    "获取路网素材区域失败": "Failed to get road material regions",
    "获取素材列表失败": "Failed to get material list",
    "获取像素账户失败": "Failed to get pixel accounts",
    "获取数据表失败": "Failed to get data tables",
    "加载静态文件失败": "Failed to load static files",
    "加载表格失败": "Failed to load sheets",
    "加载分析失败": "Failed to load analyses",
    "加载工作区失败": "Failed to load workspaces",
    "数据库名称": "Database Name",
    "请填写主机和数据库名": "Please fill in host and database name",
    "静态文件批量导出.zip": "Static Files Batch Export.zip",
    "数据库数据批量导出.zip": "Database Data Batch Export.zip",
    "BaseUrl 已更新": "BaseUrl Updated",
    "OCR文本提取": "OCR Text Extraction",
    "AI图片处理": "AI Image Processing",
    "文本": "Text",
    "名称": "Name",
    "大小": "Size",
    "来源": "Source",
    "时间": "Time",
    "元数据": "Metadata",
    "属性": "Properties",
    "字符": "chars",
    "行": "rows",
    "源表": "Source Table",
    "源更新": "Source Updated",
    "地名模式": "Place Name Mode",
    "边界模式": "Boundary Mode",
    "节点": "Nodes",
    "边": "Edges",
    "路口": "Junctions",
}

# Update translations
for k, v in all_keys.items():
    zh = v['zh'].strip()
    if '[TODO]' in v.get('en', ''):
        if zh in EN_DICT:
            v['en'] = EN_DICT[zh]
        else:
            # Try word-by-word replacement
            result = zh
            for cn_term, en_term in sorted(EN_DICT.items(), key=lambda x: -len(x[0])):
                if cn_term in result:
                    result = result.replace(cn_term, en_term)
            if not re.search(r'[\u4e00-\u9fff]', result) and result != zh:
                v['en'] = result
            elif result != zh:
                v['en'] = result  # Partial translation, still useful

# Save updated mapping
with open('scripts/i18n_data_workbench_mapping.json', 'w') as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

# Report remaining
remaining = [(k, v) for k, v in all_keys.items() if re.search(r'[\u4e00-\u9fff]', v.get('en', ''))]
print(f"EN 含中文残留: {len(remaining)} 条")
for k, v in remaining[:10]:
    print(f"  {k}: zh={v['zh'][:40]} en={v['en'][:60]}")

# Update en.json
with open('web/i18n/messages/en.json', 'r') as f:
    en = json.load(f)

for k, v in all_keys.items():
    en_text = v.get('en', v['zh'])
    if re.search(r'[\u4e00-\u9fff]', en_text):
        continue  # Skip untranslated
    parts = k.split('.')
    d = en
    for p in parts[:-1]:
        if p not in d or not isinstance(d.get(p), dict):
            d[p] = {}
        d = d[p]
    last = parts[-1]
    d[last] = en_text

with open('web/i18n/messages/en.json', 'w') as f:
    json.dump(en, f, ensure_ascii=False, indent=2)

# Update tr.json (use EN as fallback)
with open('web/i18n/messages/tr.json', 'r') as f:
    tr = json.load(f)

for k, v in all_keys.items():
    en_text = v.get('en', v['zh'])
    if re.search(r'[\u4e00-\u9fff]', en_text):
        continue
    parts = k.split('.')
    d = tr
    for p in parts[:-1]:
        if p not in d or not isinstance(d.get(p), dict):
            d[p] = {}
        d = d[p]
    last = parts[-1]
    if last not in d:
        d[last] = en_text  # Use EN as fallback

with open('web/i18n/messages/tr.json', 'w') as f:
    json.dump(tr, f, ensure_ascii=False, indent=2)

print("\n✅ 翻译已更新到 en.json 和 tr.json")
