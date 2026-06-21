#!/usr/bin/env python3
"""
脚手架 CLI 工具 —— 快速生成新模块的全部代码。

遵循 AGENTS.md 中定义的所有强制规则，生成：
  后端: Model, Schema, Controller, API 路由, 路由注册, Controller 导出
  前端: API 函数, Vue 页面 (CrudTable + useCRUD + CrudModal)

用法:
  # 交互式模式
  python scripts/scaffold.py

  # 命令行模式（最小参数）
  python scripts/scaffold.py --name tag --cn 标签

  # 带字段定义
  python scripts/scaffold.py \\
    --name announcement --cn 公告 \\
    --fields "title:str:50:标题:true,content:str:1000:内容,is_active:bool:是否激活:true"

  # 从 JSON 文件读取
  python scripts/scaffold.py --config scripts/scaffold_defs/announcement.json

字段格式: name:type:max_length:description:index
  - type: str, int, bool, float, text (Long Text)
  - max_length: 仅 str 需要，text 和 int/bool/float 可省略
  - description: 中文说明
  - index: true/false (是否建索引)，默认 false
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple


# ─── 项目根目录（从 scripts/ 向上一级） ───
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# ─── 模板中的路径常量 ───
BACKEND_DIR = PROJECT_ROOT / "app"
FRONTEND_DIR = PROJECT_ROOT / "web" / "src"


# ═══════════════════════════════════════════════════════════════════════
# 字段解析
# ═══════════════════════════════════════════════════════════════════════

def parse_field(raw: str) -> dict:
    """解析单个字段定义: name:type:max_length:description:index"""
    parts = raw.strip().split(":")
    if len(parts) < 2:
        raise ValueError(f"字段格式错误，至少需要 name:type —— 收到: {raw}")

    name, ftype = parts[0], parts[1]
    max_len = ""
    desc = ""
    index = False

    rest = parts[2:] if len(parts) > 2 else []

    # 启发式：如果 ftype 是 str/int/bool/float/text，后续按位置解析
    if ftype in ("str", "int", "bool", "float", "text"):
        if rest:
            # 尝试判断第一个是 max_length 还是 description
            if ftype == "str" and rest and rest[0].isdigit():
                max_len = rest[0]
                rest = rest[1:]
            elif ftype == "text":
                # text 不需要 max_length，跳过
                pass
            if rest:
                desc = rest[0]
                rest = rest[1:]
            if rest:
                index = rest[0].lower() in ("true", "1", "yes", "index")
    else:
        # 自定义类型（如 ENUM 名），剩余全作为描述
        if rest:
            desc = rest[0]

    return {
        "name": name,
        "type": ftype,
        "max_length": max_len,
        "description": desc or name,
        "index": index,
    }


def parse_fields(raw_fields: str) -> List[dict]:
    """解析逗号分隔的字段列表"""
    if not raw_fields.strip():
        return []
    return [parse_field(f) for f in raw_fields.split(",")]


# ═══════════════════════════════════════════════════════════════════════
# 命名工具
# ═══════════════════════════════════════════════════════════════════════

def to_snake(name: str) -> str:
    """camelCase / PascalCase → snake_case"""
    s = re.sub(r"([A-Z])", r"_\1", name)
    return s.lower().lstrip("_")


def to_pascal(name: str) -> str:
    """snake_case → PascalCase"""
    return "".join(w.capitalize() for w in name.split("_"))


def to_camel(name: str) -> str:
    """snake_case → camelCase"""
    pascal = to_pascal(name)
    return pascal[0].lower() + pascal[1:]


def to_kebab(name: str) -> str:
    """snake_case → kebab-case"""
    return name.replace("_", "-")


# ═══════════════════════════════════════════════════════════════════════
# 字段 → Model / Schema / Vue Form 代码生成
# ═══════════════════════════════════════════════════════════════════════

TORTOISE_TYPE_MAP = {
    "str": "CharField",
    "text": "TextField",
    "int": "IntField",
    "bool": "BooleanField",
    "float": "FloatField",
}

PYDANTIC_TYPE_MAP = {
    "str": "str",
    "text": "str",
    "int": "int",
    "bool": "bool",
    "float": "float",
}

NAIVE_INPUT_MAP = {
    "str": "NInput",
    "text": "NInput",  # type="textarea"
    "int": "NInputNumber",
    "bool": "NSwitch",
    "float": "NInputNumber",
}


def gen_model_field(f: dict) -> str:
    """生成 Tortoise ORM 字段定义"""
    ftype = f["type"]
    name = f["name"]
    desc = f["description"]
    tortoise_type = TORTOISE_TYPE_MAP.get(ftype, "CharField")

    parts = [f'{name} = fields.{tortoise_type}(']

    if ftype == "str" and f.get("max_length"):
        parts.append(f"max_length={f['max_length']}, ")

    if f["index"]:
        parts.append("index=True, ")

    if ftype == "bool":
        parts.append("default=False, ")

    parts.append(f'description="{desc}")')
    return "".join(parts)


def gen_schema_field(f: dict, schema_type: str) -> str:
    """生成 Pydantic Schema 字段定义"""
    ftype = f["type"]
    name = f["name"]
    desc = f["description"]
    pyd_type = PYDANTIC_TYPE_MAP.get(ftype, "str")

    is_optional = ftype == "bool" or (schema_type == "update" and name == "id")

    if name == "id" and schema_type == "update":
        return f"    {name}: int"

    if ftype == "text":
        return f'    {name}: Optional[str] = Field(None, description="{desc}")'

    if ftype == "bool":
        return f'    {name}: Optional[bool] = Field(False, description="{desc}")'

    if ftype == "float":
        if schema_type == "create":
            return f'    {name}: Optional[float] = Field(None, description="{desc}")'
        else:
            return f'    {name}: Optional[float] = Field(None, description="{desc}")'

    if ftype == "int":
        if schema_type == "create":
            return f'    {name}: Optional[int] = Field(None, description="{desc}")'
        else:
            return f'    {name}: Optional[int] = Field(None, description="{desc}")'

    # str
    if schema_type == "create":
        return f'    {name}: str = Field(..., description="{desc}", example="示例{desc}")'
    else:
        return f'    {name}: str = Field(..., description="{desc}")'


def gen_table_column(f: dict) -> str:
    """生成 CrudTable columns 定义 (JS)"""
    name = f["name"]
    desc = f["description"]
    ftype = f["type"]

    width = 120
    if ftype == "bool":
        width = 60
    elif ftype == "int" or ftype == "float":
        width = 80
    elif ftype == "text":
        width = 200

    lines = ["    {",
             f'      title: t("{desc}"), key: "{name}", width: {width}, align: "center",']
    if ftype == "text" or (ftype == "str" and int(f.get("max_length", 0) or 0) > 50):
        lines.append('      ellipsis: { tooltip: true },')
    if ftype == "bool":
        lines.append(f'      render(row) {{ return h(NTag, {{ type: row.{name} ? "success" : "default" }}, {{ default: () => row.{name} ? t("是") : t("否") }}) }},')
    lines.append("    },")
    return "\n".join(lines)


def gen_form_item(f: dict) -> str:
    """生成 NFormItem 模板片段 (Vue)"""
    name = f["name"]
    desc = f["description"]

    naive_input = NAIVE_INPUT_MAP.get(f["type"], "NInput")

    if naive_input == "NInputNumber":
        return f"""        <NFormItem label="{desc}">
          <{naive_input} v-model:value="modalForm.{name}" :placeholder="t('请输入{desc}')" clearable />
        </NFormItem>"""
    elif f["type"] == "text":
        return f"""        <NFormItem label="{desc}">
          <NInput v-model:value="modalForm.{name}" type="textarea" :placeholder="t('请输入{desc}')" clearable :autosize="{{ minRows: 3, maxRows: 8 }}" />
        </NFormItem>"""
    elif f["type"] == "bool":
        return f"""        <NFormItem label="{desc}">
          <NSwitch v-model:value="modalForm.{name}" />
        </NFormItem>"""
    else:
        return f"""        <NFormItem label="{desc}">
          <NInput v-model:value="modalForm.{name}" :placeholder="t('请输入{desc}')" clearable />
        </NFormItem>"""


def gen_search_item(f: dict) -> str:
    """生成 QueryBar 搜索字段"""
    name = f["name"]
    desc = f["description"]
    return f"""            <QueryBarItem label="{desc}" :label-width="60">
              <NInput
                v-model:value="queryItems.{name}"
                clearable
                :placeholder="t('搜索{desc}')"
                @keypress.enter="$table?.handleSearch()"
              />
            </QueryBarItem>"""


def gen_init_form(fields: List[dict]) -> str:
    """生成 initForm 对象字面量 (JS)"""
    parts = []
    for f in fields:
        if f["type"] == "bool":
            parts.append(f"{f['name']}: false")
        elif f["type"] in ("int", "float"):
            parts.append(f"{f['name']}: null")
        elif f["type"] == "text":
            parts.append(f"{f['name']}: ''")
        else:
            parts.append(f"{f['name']}: ''")
    return "{ " + ", ".join(parts) + " }"


# ═══════════════════════════════════════════════════════════════════════
# 文件生成器
# ═══════════════════════════════════════════════════════════════════════

class ScaffoldGenerator:
    def __init__(self, name: str, cn_name: str, route: str, fields: List[dict],
                 module_group: str = "system", icon: str = "material-symbols:list"):
        self.name = name                  # snake_case, e.g. "announcement"
        self.cn_name = cn_name            # 中文名, e.g. "公告"
        self.route = (route or to_kebab(name)).lstrip("/")  # e.g. "announcement" or "content/announcement"
        self.fields = fields or []
        self.module_group = module_group  # 前端 views 子目录, e.g. "system"
        self.icon = icon                  # 菜单图标

        # 派生命名
        self.Pascal = to_pascal(name)     # Announcement
        self.camel = to_camel(name)       # announcement
        self.kebab = to_kebab(name)       # announcement
        self.controller_var = f"{name}_controller"  # announcement_controller
        self.router_var = f"{name}_router"          # announcement_router
        self.table_name = name                         # announcement

    # ── 后端生成 ──

    def gen_model_code(self) -> str:
        """生成模型类代码片段（追加到 app/models/admin.py）"""
        lines = [
            f"\nclass {self.Pascal}(BaseModel, TimestampMixin):",
        ]
        for f in self.fields:
            lines.append(f"    {gen_model_field(f)}")

        lines.append("")
        lines.append("    class Meta:")
        lines.append(f'        table = "{self.table_name}"')
        lines.append("")

        return "\n".join(lines)

    def gen_schema_code(self) -> str:
        """生成完整 Schema 文件"""
        lines = [
            '"""',
            f'{self.cn_name} Schema',
            '"""',
            'from typing import Optional',
            '',
            'from pydantic import BaseModel, Field',
            '',
            '',
            f'class {self.Pascal}Create(BaseModel):',
        ]
        for f in self.fields:
            lines.append(gen_schema_field(f, "create"))

        lines.append("")
        lines.append("")
        lines.append(f'class {self.Pascal}Update(BaseModel):')
        lines.append("    id: int")
        for f in self.fields:
            lines.append(gen_schema_field(f, "update"))

        return "\n".join(lines) + "\n"

    def gen_controller_code(self) -> str:
        """生成完整 Controller 文件"""
        lines = [
            '"""',
            f'{self.cn_name} 控制器',
            '"""',
            '',
            f'from app.core.crud import CRUDBase',
            f'from app.models.admin import {self.Pascal}',
            f'from app.schemas.{self.name} import {self.Pascal}Create, {self.Pascal}Update',
            '',
            '',
            f'class {self.Pascal}Controller(CRUDBase[{self.Pascal}, {self.Pascal}Create, {self.Pascal}Update]):',
            '    def __init__(self):',
            f'        super().__init__(model={self.Pascal})',
            '',
            '',
            f'{self.controller_var} = {self.Pascal}Controller()',
            '',
        ]
        return "\n".join(lines)

    def gen_route_init_code(self) -> str:
        """生成路由包 __init__.py"""
        return f"""from fastapi import APIRouter

from .{self.name} import router

{self.router_var} = APIRouter()
{self.router_var}.include_router(router, tags=["{self.cn_name}模块"])

__all__ = ["{self.router_var}"]
"""

    def gen_route_code(self) -> str:
        """生成路由视图文件"""
        return f'''""" {self.cn_name} API 路由 """
import logging

from fastapi import APIRouter, Query
from tortoise.expressions import Q

from app.controllers.{self.name} import {self.controller_var}
from app.schemas.base import Fail, Success, SuccessExtra
from app.schemas.{self.name} import {self.Pascal}Create, {self.Pascal}Update

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/list", summary="查看{self.cn_name}列表")
async def list_{self.name}(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(10, ge=1, le=100, description="每页数量"),
):
    total, objs = await {self.controller_var}.list(page=page, page_size=page_size, order=["-updated_at"])
    data = [await obj.to_dict() for obj in objs]
    return SuccessExtra(data=data, total=total, page=page, page_size=page_size)


@router.get("/get", summary="查看{self.cn_name}详情")
async def get_{self.name}(
    id: int = Query(..., description="{self.cn_name}ID"),
):
    obj = await {self.controller_var}.get(id=id)
    if not obj:
        return Fail(code=404, msg="{self.cn_name}不存在")
    return Success(data=await obj.to_dict())


@router.post("/create", summary="创建{self.cn_name}")
async def create_{self.name}(obj_in: {self.Pascal}Create):
    await {self.controller_var}.create(obj_in=obj_in)
    return Success(msg="创建成功")


@router.post("/update", summary="更新{self.cn_name}")
async def update_{self.name}(obj_in: {self.Pascal}Update):
    existing = await {self.controller_var}.get(id=obj_in.id)
    if not existing:
        return Fail(code=404, msg="{self.cn_name}不存在")
    await {self.controller_var}.update(id=obj_in.id, obj_in=obj_in)
    return Success(msg="更新成功")


@router.delete("/delete", summary="删除{self.cn_name}")
async def delete_{self.name}(
    id: int = Query(..., description="{self.cn_name}ID"),
):
    existing = await {self.controller_var}.get(id=id)
    if not existing:
        return Fail(code=404, msg="{self.cn_name}不存在")
    await {self.controller_var}.remove(id=id)
    return Success(msg="删除成功")
'''

    # ── 前端生成 ──

    def gen_frontend_api_code(self) -> str:
        """生成前端 API 函数片段"""
        route_path = self.route
        return f"""  // {self.cn_name}
  get{self.Pascal}List: (params = {{}}) => request.get('/{route_path}/list', {{ params }}),
  get{self.Pascal}ById: (params = {{}}) => request.get('/{route_path}/get', {{ params }}),
  create{self.Pascal}: (data = {{}}) => request.post('/{route_path}/create', data),
  update{self.Pascal}: (data = {{}}) => request.post('/{route_path}/update', data),
  delete{self.Pascal}: (params = {{}}) => request.delete('/{route_path}/delete', {{ params }}),"""

    def gen_vue_page_code(self) -> str:
        """生成完整 Vue 页面 (CrudTable + useCRUD + CrudModal)"""
        # 列定义
        columns = []
        for f in self.fields:
            columns.append(gen_table_column(f))
        columns_str = "\n".join(columns)

        # 表单字段
        form_items = []
        for f in self.fields:
            form_items.append(gen_form_item(f))
        form_items_str = "\n".join(form_items)

        # QueryBar 搜索字段（取前 2 个 str 字段）
        str_fields = [f for f in self.fields if f["type"] in ("str", "text")]
        search_items = []
        for f in str_fields[:2]:
            search_items.append(gen_search_item(f))
        search_items_str = "\n".join(search_items)

        init_form = gen_init_form(self.fields)

        return f'''<script setup>
import {{ useI18n }} from 'vue-i18n'
import i18n from '~/i18n'
import {{ h, onMounted, ref }} from 'vue'
import {{
  NButton,
  NInput,
  NInputNumber,
  NSwitch,
  NTag,
  NPopconfirm,
}} from 'naive-ui'

import CommonPage from '@/components/page/CommonPage.vue'
import QueryBarItem from '@/components/query-bar/QueryBarItem.vue'
import CrudModal from '@/components/table/CrudModal.vue'
import CrudTable from '@/components/table/CrudTable.vue'
import TheIcon from '@/components/icon/TheIcon.vue'

import {{ renderIcon }} from '@/utils'
import {{ useCRUD }} from '@/composables'
import api from '@/api'

const {{ t }} = useI18n()

defineOptions({{ name: '{self.cn_name}管理' }})

const $table = ref(null)
const queryItems = ref({{}})

const {{
  modalVisible,
  modalTitle,
  modalAction,
  modalLoading,
  handleSave,
  modalForm,
  modalFormRef,
  handleEdit,
  handleDelete,
  handleAdd,
}} = useCRUD({{
  name: '{self.cn_name}',
  initForm: {init_form},
  doCreate: api.create{self.Pascal},
  doUpdate: api.update{self.Pascal},
  doDelete: api.delete{self.Pascal},
  refresh: () => $table.value?.handleSearch(),
}})

onMounted(() => {{
  $table.value?.handleSearch()
}})

const columns = [
{columns_str}
  {{
    title: t('views.network.roadNetworkWorkbench.tabs.fields.colActions'),
    key: 'actions',
    width: 120,
    align: 'center',
    fixed: 'right',
    render(row) {{
      return [
        h(
          NButton,
          {{
            size: 'small',
            type: 'primary',
            style: 'margin-right: 8px;',
            onClick: () => handleEdit(row),
          }},
          {{ default: () => t('views.workbench.label_edit'), icon: renderIcon('material-symbols:edit', {{ size: 16 }}) }},
        ),
        h(NPopconfirm, {{
          onPositiveClick: () => handleDelete({{ id: row.id }}),
        }}, {{
          trigger: () =>
            h(NButton, {{ size: 'small', type: 'error' }}, {{
              default: () => t('views.network.roadNetworkWorkbench.tabs.filter.delete'),
              icon: renderIcon('material-symbols:delete-outline', {{ size: 16 }}),
            }}),
        }}),
      ]
    }},
  }},
]
</script>

<template>
  <CommonPage :title="t('{self.cn_name}管理')">
    <template #action>
      <NButton type="primary" @click="handleAdd">
        <TheIcon icon="material-symbols:add" :size="18" class="mr-5" />新建
      </NButton>
    </template>

    <CrudTable
      ref="$table"
      v-model:query-items="queryItems"
      :columns="columns"
      :get-data="api.get{self.Pascal}List"
    >
      <template #queryBar>
{search_items_str}
      </template>
    </CrudTable>

    <CrudModal
      v-model:visible="modalVisible"
      :title="modalTitle"
      :loading="modalLoading"
      @save="handleSave"
    >
      <NForm ref="modalFormRef" :model="modalForm" label-placement="left" :label-width="100">
{form_items_str}
      </NForm>
    </CrudModal>
  </CommonPage>
</template>
'''


# ═══════════════════════════════════════════════════════════════════════
# 文件写入与注册
# ═══════════════════════════════════════════════════════════════════════

class ScaffoldWriter:
    """负责将生成的代码写入项目文件，并更新注册入口。"""

    def __init__(self, gen: ScaffoldGenerator, dry_run: bool = False):
        self.gen = gen
        self.dry_run = dry_run
        self.files_created = []
        self.files_modified = []

    def _write(self, path: Path, content: str, mode: str = "w"):
        if self.dry_run:
            self.files_created.append(str(path))
            print(f"[DRY RUN] 将创建: {path}")
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        self.files_created.append(str(path))
        print(f"   ✓ 创建: {path}")

    def _append_to_file(self, path: Path, snippet: str, marker: str | None = None):
        """追加代码片段到文件末尾（如在 marker 之后插入则更精确）"""
        if self.dry_run:
            self.files_modified.append(str(path))
            print(f"[DRY RUN] 将修改: {path}")
            return
        content = path.read_text(encoding="utf-8")

        if marker and marker in content:
            # 在 marker 行之后插入
            lines = content.split("\n")
            new_lines = []
            for line in lines:
                new_lines.append(line)
                if line.strip() == marker.strip():
                    new_lines.append(snippet)
            path.write_text("\n".join(new_lines), encoding="utf-8")
        else:
            # 追加到文件末尾
            if not content.endswith("\n"):
                content += "\n"
            content += snippet + "\n"
            path.write_text(content, encoding="utf-8")

        self.files_modified.append(str(path))
        print(f"   ✓ 修改: {path}")

    def _insert_after_imports(self, path: Path, snippet: str, anchor: str):
        """在包含 anchor 的最后一条 import 语句之后插入代码。"""
        if self.dry_run:
            self.files_modified.append(str(path))
            print(f"[DRY RUN] 将修改: {path}")
            return
        content = path.read_text(encoding="utf-8")
        lines = content.split("\n")

        # 找到最后一个匹配 anchor 的行
        last_idx = -1
        for i, line in enumerate(lines):
            if anchor in line:
                last_idx = i

        if last_idx >= 0:
            lines.insert(last_idx + 1, snippet)
        else:
            lines.append(snippet)

        path.write_text("\n".join(lines), encoding="utf-8")
        self.files_modified.append(str(path))
        print(f"   ✓ 修改: {path}")

    def write_all(self):
        gen = self.gen

        # ── 后端文件 ──

        # 1. Schema
        schema_path = BACKEND_DIR / "schemas" / f"{gen.name}.py"
        if schema_path.exists():
            print(f"   ⚠ 跳过已存在: {schema_path}")
        else:
            self._write(schema_path, gen.gen_schema_code())

        # 2. Controller
        ctrl_path = BACKEND_DIR / "controllers" / f"{gen.name}.py"
        if ctrl_path.exists():
            print(f"   ⚠ 跳过已存在: {ctrl_path}")
        else:
            self._write(ctrl_path, gen.gen_controller_code())

        # 3. API 路由包
        route_dir = BACKEND_DIR / "api" / "v1" / gen.name
        route_init = route_dir / "__init__.py"
        route_file = route_dir / f"{gen.name}.py"
        if route_init.exists():
            print(f"   ⚠ 跳过已存在: {route_init}")
        else:
            self._write(route_init, gen.gen_route_init_code())
        if route_file.exists():
            print(f"   ⚠ 跳过已存在: {route_file}")
        else:
            self._write(route_file, gen.gen_route_code())

        # 4. 模型类追加到 app/models/admin.py
        model_path = BACKEND_DIR / "models" / "admin.py"
        # 检查类是否已存在
        existing_content = model_path.read_text(encoding="utf-8")
        if f"class {gen.Pascal}(" in existing_content:
            print(f"   ⚠ 模型 {gen.Pascal} 已存在于 admin.py，跳过")
        else:
            model_code = gen.gen_model_code()
            self._append_to_file(model_path, model_code)

        # 5. 路由注册: app/api/v1/__init__.py
        v1_init = BACKEND_DIR / "api" / "v1" / "__init__.py"
        v1_content = v1_init.read_text(encoding="utf-8")

        # 添加 import
        import_line = f"from .{gen.name} import {gen.router_var}"
        if import_line not in v1_content:
            self._insert_after_imports(
                v1_init,
                import_line,
                "from .",
            )

        # 添加 include_router
        include_line = f'v1_router.include_router({gen.router_var}, prefix="/{gen.route}", dependencies=[DependPermission])'
        if include_line not in v1_content:
            # 找到最后一个 v1_router.include_router 之后插入
            self._append_after_last_include(v1_init, include_line)

        # 6. Controller 导出: app/controllers/__init__.py
        ctrl_init = BACKEND_DIR / "controllers" / "__init__.py"
        export_line = f"from .{gen.name} import {gen.controller_var} as {gen.controller_var}"
        if export_line not in ctrl_init.read_text(encoding="utf-8"):
            self._append_to_file(ctrl_init, export_line)

        # ── 前端文件 ──

        # 7. API 函数: web/src/api/index.js
        api_path = FRONTEND_DIR / "api" / "index.js"
        api_content = api_path.read_text(encoding="utf-8")
        api_snippet = gen.gen_frontend_api_code()
        if f"get{gen.Pascal}List" not in api_content:
            self._append_to_file(api_path, api_snippet)
        else:
            print(f"   ⚠ API 函数 get{gen.Pascal}List 已存在，跳过")

        # 8. Vue 页面
        page_dir = FRONTEND_DIR / "views" / gen.module_group / gen.name
        page_path = page_dir / "index.vue"
        if page_path.exists():
            print(f"   ⚠ 跳过已存在: {page_path}")
        else:
            self._write(page_path, gen.gen_vue_page_code())

        print(f"\n📊 共创建 {len(self.files_created)} 个文件，修改 {len(self.files_modified)} 个文件。")

    def _append_after_last_include(self, path: Path, line: str):
        """在最后一个 v1_router.include_router(...) 之后插入行。"""
        content = path.read_text(encoding="utf-8")
        lines = content.split("\n")

        # 找最后一个 include_router
        last_include_idx = -1
        for i, l in enumerate(lines):
            if "v1_router.include_router(" in l:
                last_include_idx = i

        if last_include_idx >= 0:
            lines.insert(last_include_idx + 1, line)
            # 确保末尾有空行
            if lines[last_include_idx + 2].strip() != "":
                lines.insert(last_include_idx + 2, "")
        else:
            lines.append(line)

        path.write_text("\n".join(lines), encoding="utf-8")
        if not self.dry_run:
            self.files_modified.append(str(path))
            print(f"   ✓ 修改: {path}")

    def print_summary(self):
        print(f"\n{'═' * 60}")
        print("  生成完毕！后续手动步骤：")
        print(f"{'═' * 60}")
        print(f"  1. 数据库迁移: make migrate && make upgrade")
        print(f"  2. 菜单配置:   后台「菜单管理」→ 添加菜单")
        print(f"                 路径: /{self.gen.name}")
        print(f"                 组件: /{self.gen.module_group}/{self.gen.name}")
        print(f"  3. 角色权限:   给角色分配新菜单 + API 权限")
        print(f"  4. 前端构建:   cd web && pnpm install && pnpm build")
        print(f"  5. (可选) 种子数据: app/core/init_app.py")
        print(f"{'═' * 60}\n")


# ═══════════════════════════════════════════════════════════════════════
# CLI 入口
# ═══════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="vue-fastapi-admin 模块脚手架",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python scripts/scaffold.py --name tag --cn 标签 --fields "name:str:50:名称:true,color:str:20:颜色"
  python scripts/scaffold.py --name announcement --cn 公告
  python scripts/scaffold.py --config scaffold_defs/gallery.json
        """,
    )
    parser.add_argument("--name", help="模块名（snake_case），如 announcement")
    parser.add_argument("--cn", dest="cn_name", help="中文名，如 公告")
    parser.add_argument("--route", help="路由前缀，默认从 name 推导（kebab-case）")
    parser.add_argument("--fields", help="字段列表，格式: name:type:max_length:desc:index,...")
    parser.add_argument("--group", default="system", help="前端 views 子目录，默认 system")
    parser.add_argument("--icon", default="material-symbols:list", help="菜单图标")
    parser.add_argument("--config", help="JSON 配置文件路径（相对于项目根目录）")
    parser.add_argument("--dry-run", action="store_true", help="只预览，不写入文件")
    parser.add_argument("--interactive", "-i", action="store_true", help="交互式模式")
    args = parser.parse_args()

    # ── 模式 1: JSON 配置文件 ──
    if args.config:
        config_path = PROJECT_ROOT / args.config
        if not config_path.exists():
            print(f"❌ 配置文件不存在: {config_path}")
            sys.exit(1)
        config = json.loads(config_path.read_text(encoding="utf-8"))
        name = config["name"]
        cn_name = config["cn_name"]
        route = config.get("route", to_kebab(name))
        fields = config.get("fields", [])
        module_group = config.get("group", "system")
        icon = config.get("icon", "material-symbols:list")
    # ── 模式 2: 交互式 ──
    elif args.interactive or (not args.name and not args.cn_name and not args.config):
        name, cn_name, route, fields, module_group, icon = interactive_mode()
    # ── 模式 3: CLI 参数 ──
    else:
        if not args.name or not args.cn_name:
            parser.error("--name 和 --cn 是必填参数（或使用 --config / -i 交互模式）")
        name = args.name
        cn_name = args.cn_name
        route = args.route or to_kebab(name)
        fields = parse_fields(args.fields) if args.fields else []
        module_group = args.group
        icon = args.icon

    # 验证 name 格式
    if not re.match(r"^[a-z][a-z0-9_]*$", name):
        print(f"❌ 模块名必须为 snake_case: {name}")
        sys.exit(1)

    print(f"\n{'═' * 60}")
    print(f"  脚手架生成: {name} ({cn_name})")
    print(f"  路由前缀:   /{route.lstrip('/')}")
    print(f"  字段数量:   {len(fields)}")
    print(f"  前端分组:   {module_group}")
    print(f"  {'[DRY RUN] ' if args.dry_run else ''}")
    print(f"{'═' * 60}\n")

    gen = ScaffoldGenerator(
        name=name,
        cn_name=cn_name,
        route=route,
        fields=fields,
        module_group=module_group,
        icon=icon,
    )

    writer = ScaffoldWriter(gen, dry_run=args.dry_run or False)
    writer.write_all()

    if not args.dry_run:
        writer.print_summary()


def interactive_mode() -> Tuple[str, str, str, List[dict], str, str]:
    """交互式收集信息"""
    print("\n  ▸ vue-fastapi-admin 脚手架 (交互模式)\n")

    name = input("  模块名 (snake_case, 如 announcement): ").strip()
    if not re.match(r"^[a-z][a-z0-9_]*$", name):
        print(f"  ❌ 模块名必须为 snake_case")
        sys.exit(1)

    cn_name = input("  中文名 (如 公告): ").strip()
    if not cn_name:
        print(f"  ❌ 中文名不能为空")
        sys.exit(1)

    route = input(f"  路由前缀 [/{to_kebab(name)}]: ").strip()
    if not route:
        route = to_kebab(name)

    module_group = input("  前端 views 子目录 [system]: ").strip() or "system"

    print("\n  字段定义 (格式: name:type:max_length:desc:index)")
    print("    type = str | int | bool | float | text (Long Text)")
    print("    示例: name:str:50:名称:true")
    print("    输入空行结束字段定义。\n")

    fields = []
    i = 1
    while True:
        raw = input(f"  字段 #{i}: ").strip()
        if not raw:
            break
        try:
            fields.append(parse_field(raw))
            i += 1
        except ValueError as e:
            print(f"  ⚠ {e}")

    icon = input("  菜单图标 [material-symbols:list]: ").strip() or "material-symbols:list"

    return name, cn_name, route, fields, module_group, icon


if __name__ == "__main__":
    main()
