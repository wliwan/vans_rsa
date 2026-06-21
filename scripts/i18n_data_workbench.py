#!/usr/bin/env python3
"""
数据工作台国际化脚本 — 提取硬编码中文，生成 i18n 密钥，应用到语言包和 Vue 源码。
"""

import hashlib
import json
import re
import os
import sys
from collections import OrderedDict
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# 语言包路径
I18N_DIR = PROJECT_ROOT / "web" / "i18n" / "messages"
CN_FILE = I18N_DIR / "cn.json"
EN_FILE = I18N_DIR / "en.json"
TR_FILE = I18N_DIR / "tr.json"

# 要处理的 Vue 文件
VUE_FILES = [
    "web/src/views/statistic-center/data-workbench/index.vue",
    "web/src/views/statistic-center/excel-data/index.vue",
    "web/src/views/statistic-center/report/index.vue",
    "web/src/views/statistic-center/doc-workbench/index.vue",
]

# ── Key 生成 ──
def make_key(prefix: str, chinese_text: str) -> str:
    """生成 `{prefix}_cn_{md5[:8]}` 格式的 key。"""
    h = hashlib.md5(chinese_text.encode('utf-8')).hexdigest()[:8]
    return f"{prefix}_cn_{h}"

# ── 英文翻译词典 ──
EN_DICT = {
    # 通用按钮/标签
    "删除": "Delete",
    "编辑": "Edit",
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
    "开始生成": "Generate",
    "开始分析": "Start Analysis",
    "确认克隆": "Clone",
    "确认删除": "Confirm Delete",
    "确认清空": "Confirm Clear",
    "查看": "View",
    "搜索": "Search",
    "下载": "Download",
    "上传": "Upload",
    "关闭预览": "Close Preview",
    "新标签页打开": "Open in New Tab",
    "复制短链接": "Copy Short Link",
    "加载中...": "Loading...",
    "加载中": "Loading",
    "暂无数据": "No Data",
    "暂无": "None",
    "无": "None",
    "关闭": "Close",
    "共": "Total",
    "条": "items",
    "已选": "Selected",
    "选择": "Select",
    "未选择": "Not Selected",
    "已全选": "All Selected",
    "部分选中": "Partially Selected",
    "项": "items",
    "成功": "Success",
    "失败": "Failed",
    "处理中": "Processing",
    "时间": "Time",
    "大小": "Size",
    "来源": "Source",
    "属性": "Properties",
    "元数据": "Metadata",
    "文档名称": "Document Name",
    "文档内容": "Document Content",
    "工作区": "Workspace",
    "新建工作区": "New Workspace",
    "编辑工作区": "Edit Workspace",
    "数据工作区": "Data Workspace",
    "数据工作台": "Data Workbench",
    "统计中心": "Statistics Center",
    "报告": "Report",
    "报告生成": "Report Generation",
    "生成报告": "Generate Report",
    "生成文书": "Generate Document",
    "从文本创建文档": "Create Document from Text",
    "新建文本": "New Text",
    "基本属性": "Basic Properties",
    "描述": "Description",
    "名称": "Name",
    "短链接（公开访问）": "Short Link (Public Access)",
    "短链接不可用": "Short Link Unavailable",
    "短链接已复制": "Short Link Copied",
    "EXIF 信息": "EXIF Info",
    "分辨率": "Resolution",
    "色彩": "Color",
    "位深": "Bit Depth",
    "宽度": "Width",
    "高度": "Height",
    # 数据相关
    "原始表格": "Original Sheets",
    "原始表格目录": "Original Sheets Directory",
    "拆解分析表格": "Analysis Sheets",
    "分析名称": "Analysis Name",
    "关联分析": "Correlation Analysis",
    "分析": "Analysis",
    "暂无原始表格": "No Original Sheets",
    "暂无分析结果": "No Analysis Results",
    "暂无文档": "No Documents",
    "暂无文件": "No Files",
    "暂无数据源": "No Data Sources",
    "暂无工作区": "No Workspaces",
    "暂无分析文档": "No Analysis Documents",
    "分析表格 A": "Analysis Sheet A",
    "分析表格 B": "Analysis Sheet B",
    "表格 A": "Sheet A",
    "表格 B": "Sheet B",
    "无区域选中提示": "No Region Selected",
    "请选择": "Please Select",
    "请先选择": "Please First Select",
    # 提示/消息
    "请先选择工作区": "Please select a workspace first",
    "请先选择文件": "Please select files first",
    "请先选择数据": "Please select data first",
    "请先选择图片文件": "Please select image files first",
    "请先选择原始表格": "Please select original sheets first",
    "请先选择原始文档": "Please select original documents first",
    "请先选择分析文档": "Please select analysis documents first",
    "请先选择要复制的文档": "Please select documents to copy first",
    "请先选择要复制的数据": "Please select data to copy first",
    "请先选择要导出的数据": "Please select data to export first",
    "请选择工作区": "Please select a workspace",
    "请选择目标工作区": "Please select target workspace",
    "请选择数据工作区": "Please select data workspace",
    "请选择AI代理": "Please select an AI proxy",
    "请选择账户和数据表": "Please select account and table",
    "请选择要导入的素材": "Please select materials to import",
    "请选择报告": "Please select a report",
    "请选择数据表": "Please select a data table",
    "请选择区域": "Please select a region",
    "请选择路网文件": "Please select road network files",
    "请至少选择一个表": "Please select at least one table",
    "请至少选择一个路网文件": "Please select at least one road network file",
    "请选中 2 个原始表格": "Please select 2 original sheets",
    "请选择两个分析表格": "Please select 2 analysis sheets",
    "请填写主机和数据库名": "Please fill in host and database name",
    "请填写主机、数据库和用户名": "Please fill in host, database and username",
    "请选择租户（像素账户）": "Please select tenant (pixel account)",
    "请选择租户和数据表": "Please select tenant and data table",
    "请选择要删除的文档": "Please select documents to delete",
    "请选择要删除的表格": "Please select sheets to delete",
    "请选择要导出的文档": "Please select documents to export",
    "请选择要导出的表格": "Please select sheets to export",
    "请先上传图片文件": "Please upload image files first",
    "请先上传 SQLite 文件": "Please upload SQLite file first",
    "请选择要导入的表": "Please select tables to import",
    "至少需要 2 个分析表格": "At least 2 analysis sheets required",
    "未选中任何数据源": "No data source selected",
    "请至少选择一个数据源": "Please select at least one data source",
    "请至少选择一项数据": "Please select at least one item",
    "当前目录没有图片文件，请先上传图片": "No image files in current directory, please upload first",
    "所选文件不含图片": "Selected files contain no images",
    "请先选择要分析的文档": "Please select documents to analyze first",
    "报告内容为空": "Report content is empty",
    "无法打开打印窗口，请检查浏览器弹窗设置": "Cannot open print window, please check browser popup settings",
    "该工作区暂无数据源，请先在数据工作台中上传数据": "This workspace has no data sources, please upload data in Data Workbench first",
    "请选择左侧报告": "Please select a report on the left",
    "请选择左侧工作区": "Please select a workspace on the left",
    # 操作结果
    "上传失败": "Upload failed",
    "删除成功": "Delete successful",
    "删除失败": "Delete failed",
    "批量删除成功": "Batch delete successful",
    "批量删除失败": "Batch delete failed",
    "批量导出失败": "Batch export failed",
    "导出失败": "Export failed",
    "导出成功": "Export successful",
    "导入成功": "Import successful",
    "导入失败": "Import failed",
    "下载失败": "Download failed",
    "复制失败": "Copy failed",
    "复制完成": "Copy completed",
    "克隆成功": "Clone successful",
    "克隆失败": "Clone failed",
    "更新失败": "Update failed",
    "创建失败": "Create failed",
    "保存失败": "Save failed",
    "上传完成": "Upload complete",
    "处理完成": "Processing complete",
    "生成失败": "Generation failed",
    "预览失败": "Preview failed",
    "连接失败": "Connection failed",
    "连接成功": "Connection successful",
    "解析失败": "Parse failed",
    "加载静态文件失败": "Failed to load static files",
    "加载表格失败": "Failed to load sheets",
    "加载分析失败": "Failed to load analyses",
    "加载工作区失败": "Failed to load workspaces",
    "加载报告失败": "Failed to load reports",
    "加载报告内容失败": "Failed to load report content",
    "加载素材失败": "Failed to load materials",
    "加载区域列表失败": "Failed to load region list",
    "获取路网区域失败": "Failed to get road network regions",
    "获取路网列表失败": "Failed to get road network list",
    "获取路网素材区域失败": "Failed to get road material regions",
    "获取素材列表失败": "Failed to get material list",
    "获取像素账户失败": "Failed to get pixel accounts",
    "获取数据表失败": "Failed to get data tables",
    "获取数据源失败": "Failed to get data sources",
    "AI处理失败": "AI processing failed",
    "AI处理完成": "AI processing completed",
    "OpenCV处理失败": "OpenCV processing failed",
    "OCR提取失败": "OCR extraction failed",
    "OCR提取完成": "OCR extraction completed",
    "关联分析失败": "Correlation analysis failed",
    "关联分析完成": "Correlation analysis completed",
    "分析完成": "Analysis completed",
    "文档AI分析完成": "Document AI analysis completed",
    "AI图片处理完成": "AI image processing completed",
    "报告生成成功": "Report generated successfully",
    "报告生成失败": "Report generation failed",
    "文档创建成功": "Document created successfully",
    # 操作
    "AI图片处理": "AI Image Processing",
    "AI 图片优化": "AI Image Optimization",
    "OpenCV 图片处理": "OpenCV Image Processing",
    "OCR提取": "OCR Extraction",
    "OCR文本提取": "OCR Text Extraction",
    "CV处理": "CV Processing",
    "目标工作区": "Target Workspace",
    "复制到工作区": "Copy to Workspace",
    "复制文件到工作区": "Copy Files to Workspace",
    "复制文档到工作区": "Copy Documents to Workspace",
    "复制数据到其他工作区": "Copy Data to Other Workspace",
    "仅创建数据库记录指向同一文件，不拷贝物理文件。": "Only creates database records pointing to the same file, no physical copy.",
    "更改 BaseUrl": "Change BaseUrl",
    "BaseUrl": "BaseUrl",
    "BaseUrl 已更新": "BaseUrl Updated",
    "如 http://rsatest.vanstk.com:9999": "e.g. http://rsatest.vanstk.com:9999",
    "设置公网访问基础地址，所有静态文件短链接将使用此地址作为前缀。": "Set public access base URL. All static file short links will use this as prefix.",
    "留空则自动使用当前访问地址。": "Leave empty to auto-detect from current access URL.",
    "保存": "Save",
    "测试连接": "Test Connection",
    "选择区域后加载路网文件": "Select a region to load road network files",
    "支持导入路网拓扑统计信息（节点数 / 边数 / 道路等级分布等）": "Supports importing road network topology stats (nodes / edges / road class distribution etc.)",
    "加载路网文件列表...": "Loading road network file list...",
    "已选": "Selected",
    "个路网文件": "road network files",
    "地名模式": "Place Name Mode",
    "边界模式": "Boundary Mode",
    "节点": "Nodes",
    "边": "Edges",
    "路口": "Junctions",
    "等级": "Levels",
    "源表:": "Source Table:",
    "源更新:": "Source Updated:",
    "已导出": "Exported",
    "个文件": "files",
    "已删除": "Deleted",
    "条数据库数据": "database records",
    "成功上传": "Successfully uploaded",
    "个文件": "files",
    "确认删除已选中的": "Confirm delete selected",
    "个分析表格？": "analysis sheets?",
    "确认删除选中的": "Confirm delete selected",
    "个文档？": "documents?",
    "条数据库数据？": "database records?",
    "个文件？": "files?",
    "确认清空当前工作区的所有分析表格？": "Confirm clear all analysis sheets in this workspace?",
    "确认清空当前工作区的所有AI分析文档？": "Confirm clear all AI analysis documents in this workspace?",
    "确认删除该工作区及所有数据？": "Confirm delete this workspace and all data?",
    "导入 MySQL 数据": "Import MySQL Data",
    "导入MySQL数据": "Import MySQL Data",
    "导入SQLite数据": "Import SQLite Data",
    "导入 SQLite 数据": "Import SQLite Data",
    "导入像素数据": "Import Pixel Data",
    "导入像素平台数据": "Import Pixel Platform Data",
    "导入路网数据": "Import Road Network Data",
    "导入路网统计数据": "Import Road Network Stats",
    "从路网素材导入": "Import from Road Materials",
    "从路网素材导入图片": "Import Images from Road Materials",
    "数据库导入数据": "Database Imported Data",
    "数据库数据批量导出.zip": "Database Data Batch Export.zip",
    "静态文件批量导出.zip": "Static Files Batch Export.zip",
    "暂无数据库导入数据": "No Database Imported Data",
    "暂无路网素材区域": "No Road Material Regions",
    "该区域暂无素材": "No Materials in This Region",
    "该区域暂无路网数据": "No Road Network Data in This Region",
    "选择要导入的表（可多选）：": "Select tables to import (multiple allowed):",
    "请先选择区域以加载该区域下的路网文件": "Please select a region first to load road network files",
    "将复制": "Will copy",
    "项数据库导入数据到目标工作区": "database records to target workspace",
    "选择区域": "Select Region",
    "选择国家 / 行政区 / 城市": "Select Country / State / City",
    "选择路网文件": "Select Road Network Files",
    "选择像素账户": "Select Pixel Account",
    "搜索并选择有路网数据的区域…": "Search and select regions with road network data…",
    "全部区域": "All Regions",
    "导入": "Import",
    "个路网统计": "road network stats",
    "表格数据": "Sheet Data",
    "文档数据": "Document Data",
    "数据库数据": "Database Data",
    "静态文件数据": "Static File Data",
    "静态文件": "Static Files",
    "数据源": "Data Sources",
    "总字数": "Total Characters",
    "Token 估算": "Token Estimate",
    "字符": "chars",
    "行": "rows",
    "源表": "Source Table",
    "上传文件到": "Upload files to",
    "原始文档": "Original Documents",
    "AI分析文档": "AI Analysis Documents",
    "目录": "directory",
    "拖拽文件到此处或点击选择，支持批量上传": "Drag files here or click to select, batch upload supported",
    "点击或拖拽文件到此区域上传（支持多选）": "Click or drag files to this area to upload (multi-select supported)",
    "上传 Excel 或 CSV 文件开始分析": "Upload Excel or CSV files to start analysis",
    "上传 txt / pdf / word / ppt 文档开始分析": "Upload txt / pdf / word / ppt documents to start analysis",
    "上传原始表格": "Upload Original Sheets",
    "上传文档": "Upload Documents",
    "点击或拖拽文件到此区域上传": "Click or drag files to this area to upload",
    "支持 .sqlite / .sqlite3 / .db 格式": "Supports .sqlite / .sqlite3 / .db formats",
    "粘贴 CSV 文本（含表头行）": "Paste CSV text (with header row)",
    "CSV导入成功": "CSV Import Successful",
    "CSV 文本内容": "CSV Text Content",
    "点击上方按钮导入 MySQL / SQLite / 像素平台 / 路网数据": "Click buttons above to import MySQL / SQLite / Pixel / Road Network data",
    "AI分析:": "AI Analysis:",
    "关联分析:": "Correlation Analysis:",
    "预览统计": "Preview Stats",
    "（每个路网生成一份汇总 + 一份道路等级明细，共 2 个 CSV 文档）": "(Generates 1 summary + 1 road class detail per network, 2 CSV docs total)",
    "确认清空": "Confirm Clear",
    "确认删除该文档？": "Confirm delete this document?",
    "清除确认": "Clear Confirm",
    "编辑文档 - ": "Edit Document - ",
    "输入文本/Markdown内容...": "Enter text/Markdown content...",
    "请输入文档内容": "Please enter document content",
    "选择 AI 代理": "Select AI Proxy",
    "AI 代理": "AI Proxy",
    "分享": "Share",
    "全选": "Select All",
    "全部删除": "Delete All",
    "复制到": "Copy To",
    "批量上传失败": "Batch Upload Failed",
    "图片加载失败": "Image Load Failed",
    # doc-workbench 特有
    "加载数据源...": "Loading data sources...",
    "数据源加载失败": "Failed to load data sources",
    "导出${type}失败": "Failed to export ${type}",
    "生成报告：": "Generate Report: ",
    "确认删除该报告及其所有内容？": "Confirm delete this report and all its contents?",
    "当前报告修改未保存": "Current report changes not saved",
    "确认放弃未保存的修改？": "Confirm discard unsaved changes?",
    "报告名称": "Report Name",
    "克隆报告": "Clone Report",
    "报告预览": "Report Preview",
    "将复制报告": "Will copy report",
    "新报告名称": "New Report Name",
    "新名称": "New Name",
    "如：会议纪要.md": "e.g.: meeting-notes.md",
    "输入文书名称": "Enter document name",
    "选择 Excel 数据工作区": "Select Excel Data Workspace",
    "选择数据工作区": "Select Data Workspace",
    "对原始表格执行 AI 分析后生成": "Generated from AI analysis of original sheets",
    "对文档执行 AI 分析后生成": "Generated from AI analysis of documents",
    "选择分析框架": "Select Analysis Framework",
    "选择 AI 代理": "Select AI Proxy",
    "辅助 Skill（可选）": "Auxiliary Skill (optional)",
    "额外的分析要求": "Additional Analysis Requirements",
    "输入额外的分析要求或提示词...": "Enter additional analysis requirements or prompts...",
    "选择 Skill 作为分析框架": "Select Skill as Analysis Framework",
    "选择 Skill 作为处理框架": "Select Skill as Processing Framework",
    "选择操作": "Select Operation",
    "AI 图片优化处理": "AI Image Optimization Processing",
    "输入处理提示词，或选择 Skill 自动填充": "Enter processing prompt, or select Skill for auto-fill",
    "描述你想要的图片处理效果，如：提升画质、增强色彩、去雾...": "Describe desired image processing effect, e.g.: enhance quality, boost colors, dehaze...",
    "额外的分析要求...": "Additional requirements...",
    "工作区名称": "Workspace Name",
    "分析结果名称": "Analysis Result Name",
    "输入文档名称": "Enter Document Name",
    "请输入文档名称": "Please Enter Document Name",
    "输入元数据描述...": "Enter metadata description...",
    "选择用户": "Select Users",
    "搜索工作区...": "Search workspace...",
    "左边距": "Left Margin",
    "右边距": "Right Margin",
    "上边距": "Top Margin",
    "下边距": "Bottom Margin",
    "分析表格关联分析": "Analysis Sheet Correlation",
    "数据库名": "Database Name",
    "主机地址": "Host Address",
    "端口": "Port",
    "用户名": "Username",
    "密码": "Password",
    "文件名称": "File Name",
    "像素": "Pixel",
    "像素账户": "Pixel Account",
    "选择表格A": "Select Sheet A",
    "选择表格B": "Select Sheet B",
    "选择原始表格": "Select Original Sheet",
    "选择分析表格": "Select Analysis Sheet",
    "选择分析表格B": "Select Analysis Sheet B",
    "选择文档": "Select Document",
    "选择Skill": "Select Skill",
    "选择预设Skill": "Select Preset Skill",
    "上传 Excel 文件": "Upload Excel File",
}


def translate_cn_to_en(text: str) -> str:
    """用词典翻译中文→英文，逐词替换。"""
    if not text or not re.search(r'[\u4e00-\u9fff]', text):
        return text
    
    # 精确匹配
    if text.strip() in EN_DICT:
        return EN_DICT[text.strip()]
    
    # 尝试带模板变量的匹配
    result = text
    # 按长度降序替换，避免短词先替换长词的一部分
    sorted_keys = sorted(EN_DICT.keys(), key=len, reverse=True)
    for cn in sorted_keys:
        if cn in result:
            result = result.replace(cn, EN_DICT[cn])
    
    # 如果还有中文残留，标记需要手动翻译
    if re.search(r'[\u4e00-\u9fff]', result):
        result = f"[TODO] {text}"
    
    return result


def extract_hardcoded_chinese(filepath: str) -> list[dict]:
    """从 Vue 文件中提取所有硬编码中文字符串（包括模板和脚本）。"""
    filepath = PROJECT_ROOT / filepath
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    lines = content.split('\n')
    results = []
    
    for i, line in enumerate(lines, 1):
        if not re.search(r'[\u4e00-\u9fff]', line):
            continue
        
        # 跳过已使用 t() 或 i18n.global.t() 的行
        if re.search(r'\bt\(', line) or re.search(r'i18n\.global\.t\(', line):
            continue
        
        stripped = line.strip()
        # 跳过纯注释
        if stripped.startswith('//') or stripped.startswith('<!--') or stripped.startswith('/*') or stripped.startswith('*'):
            continue
        
        # 提取中文文本
        # 模板中的纯文本: >中文文本<
        for m in re.finditer(r'>([^<]*[\u4e00-\u9fff]+[^<]*)<', line):
            text = m.group(1).strip()
            if text and not re.match(r'^\s*\{\{', text):
                results.append({'line': i, 'text': text, 'type': 'template_text', 'context': line.strip()[:120]})
        
        # 脚本中的字符串: '中文' 或 "中文"
        for m in re.finditer(r"'([^']*[\u4e00-\u9fff]+[^']*)'", line):
            text = m.group(1).strip()
            if text and 'defineOptions' not in text:
                results.append({'line': i, 'text': text, 'type': 'js_string', 'context': line.strip()[:120]})
        
        for m in re.finditer(r'"([^"]*[\u4e00-\u9fff]+[^"]*)"', line):
            text = m.group(1).strip()
            if text and 'defineOptions' not in text and 'import' not in stripped:
                results.append({'line': i, 'text': text, 'type': 'js_string', 'context': line.strip()[:120]})
        
        # 模板中的属性: title="中文" 或 placeholder="中文"
        for m in re.finditer(r'(?:title|placeholder|label)="([^"]*[\u4e00-\u9fff]+[^"]*)"', line):
            text = m.group(1).strip()
            if text and 't(' not in text:
                results.append({'line': i, 'text': text, 'type': 'template_attr', 'attr': m.group(0)[:m.group(0).index('=')], 'context': line.strip()[:120]})
    
    # 去重
    seen = set()
    unique = []
    for r in results:
        # 构造唯一的 key（包含文本和类型）
        key = (r['text'], r['type'])
        if key not in seen:
            seen.add(key)
            unique.append(r)
    return unique


def classify_key(text: str) -> str:
    """根据文本内容分类为 label/message/placeholder/title。"""
    t = text.strip()
    if t.endswith('...') or t.endswith('…') or '选择' in t and ('请' in t or '输入' in t or '如' in t) or t.startswith('如 ') or t.startswith('搜索') or t.startswith('描述'):
        return 'placeholder'
    if '成功' in t or '失败' in t or '完成' in t or '出错' in t or '错误' in t:
        return 'message'
    if t.startswith('确认') or t.startswith('该'):
        return 'message'
    # 检查是否是完整的句子/消息
    if len(t) > 12 and ('。' in t or '？' in t or '！' in t or '：' in t):
        if '请' in t[:4] or '确认' in t[:4]:
            return 'message'
        return 'label'
    return 'label'


def main():
    # 步骤1: 提取所有硬编码中文
    print("=" * 60)
    print("步骤1: 提取硬编码中文字符串")
    print("=" * 60)
    
    all_keys = {}
    file_strings = {}  # {filepath: [(line, text, key, type, attr), ...]}
    
    for vf in VUE_FILES:
        results = extract_hardcoded_chinese(vf)
        file_strings[vf] = []
        print(f"\n📄 {vf} ({len(results)} 处)")
        for r in results:
            text = r['text']
            prefix = classify_key(text)
            key_base = 'views.statistic-center'
            key = f"{key_base}.{make_key(prefix, text)}"
            
            # 检查是否已存在
            if key not in all_keys:
                all_keys[key] = {
                    'zh': text,
                    'en': translate_cn_to_en(text),
                }
            
            file_strings[vf].append({
                'line': r['line'],
                'text': text,
                'key': key,
                'type': r['type'],
                'attr': r.get('attr', ''),
                'context': r['context'],
            })
            print(f"  L{r['line']:4d}  {prefix}/cn_{hashlib.md5(text.encode()).hexdigest()[:8]}  {text[:60]}")
    
    print(f"\n📊 总计: {len(all_keys)} 个唯一 key")
    
    # 步骤2: 读取现有 cn.json 并合并
    print("\n" + "=" * 60)
    print("步骤2: 更新 cn.json 语言包")
    print("=" * 60)
    
    with open(CN_FILE, 'r', encoding='utf-8') as f:
        cn = json.load(f)
    
    added_cn = 0
    skipped_cn = 0
    for key, val in all_keys.items():
        parts = key.split('.')
        d = cn
        exists = True
        for p in parts[:-1]:
            if p in d and isinstance(d[p], dict):
                d = d[p]
            else:
                if p not in d:
                    d[p] = {}
                d = d[p]
                exists = False
                break
        last = parts[-1]
        if exists and last in d:
            skipped_cn += 1
            continue
        d[last] = val['zh']
        added_cn += 1
    
    with open(CN_FILE, 'w', encoding='utf-8') as f:
        json.dump(cn, f, ensure_ascii=False, indent=2)
    
    print(f"  新增: {added_cn} 条, 跳过(已存在): {skipped_cn} 条")
    
    # 步骤3: 更新 en.json
    print("\n" + "=" * 60)
    print("步骤3: 更新 en.json 语言包")
    print("=" * 60)
    
    with open(EN_FILE, 'r', encoding='utf-8') as f:
        en = json.load(f)
    
    added_en = 0
    for key, val in all_keys.items():
        parts = key.split('.')
        d = en
        for p in parts[:-1]:
            if p not in d or not isinstance(d.get(p), dict):
                d[p] = {}
            d = d[p]
        last = parts[-1]
        if last not in d:
            d[last] = val['en']
            added_en += 1
    
    with open(EN_FILE, 'w', encoding='utf-8') as f:
        json.dump(en, f, ensure_ascii=False, indent=2)
    
    print(f"  新增: {added_en} 条英文翻译")
    
    # 步骤4: 检查是否需要手动翻译的项
    todo_count = sum(1 for v in all_keys.values() if '[TODO]' in v['en'])
    if todo_count:
        print(f"\n  ⚠️  {todo_count} 条需要手动翻译（标记为 [TODO]）:")
        for key, val in all_keys.items():
            if '[TODO]' in val['en']:
                print(f"    {key}: {val['zh']}")
    
    # 输出 key 映射 - 供后续 Vue 文件更新使用
    mapping_file = PROJECT_ROOT / "scripts" / "i18n_data_workbench_mapping.json"
    with open(mapping_file, 'w', encoding='utf-8') as f:
        json.dump({
            'all_keys': all_keys,
            'file_strings': file_strings,
        }, f, ensure_ascii=False, indent=2)
    
    print(f"\n✅ Key 映射已保存到: {mapping_file}")
    print(f"   下一步: 运行 scripts/i18n_apply_to_vue.py 更新 Vue 文件")


if __name__ == '__main__':
    main()
