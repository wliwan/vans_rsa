# Vue-FastAPI-Admin (VFA) 开发指导

## 框架概述

Vue-FastAPI-Admin 是基于 **FastAPI + Vue3 + Naive UI** 的现代化前后端分离开发平台，融合了 RBAC 权限管理、动态路由和 JWT 鉴权。

### 技术栈

| 层 | 技术 | 版本要求 |
|---|---|---|
| 后端框架 | FastAPI | 0.111.0 |
| ORM | Tortoise ORM | 0.23.0 |
| 数据校验 | Pydantic | 2.10.5 |
| 密码加密 | argon2 (passlib) | 1.7.4 |
| JWT | PyJWT | 2.10.1 |
| 日志 | Loguru | 0.7.3 |
| 数据库迁移 | Aerich | 0.8.1 |
| 前端框架 | Vue 3 + Vite | node 18.8.0+ |
| UI 库 | Naive UI | - |
| 状态管理 | Pinia | - |
| CSS 方案 | UnoCSS | - |
| 包管理 | pnpm | - |

### 项目目录结构

```
├── app/                          # 后端应用
│   ├── api/                      # API 路由层
│   │   ├── __init__.py           # api_router 总入口（/api）
│   │   └── v1/                   # v1 版本路由
│   │       ├── __init__.py       # v1_router 注册所有子路由
│   │       ├── apis/             # API 管理接口
│   │       ├── auditlog/         # 审计日志接口
│   │       ├── base/             # 基础接口（登录、用户信息、菜单等）
│   │       ├── depts/            # 部门管理接口
│   │       ├── menus/            # 菜单管理接口
│   │       ├── roles/            # 角色管理接口
│   │       └── users/            # 用户管理接口
│   ├── controllers/              # 控制器层（业务逻辑）
│   │   ├── __init__.py           # 导出所有控制器
│   │   ├── api.py                # ApiController
│   │   ├── dept.py               # DeptController
│   │   ├── menu.py               # MenuController
│   │   ├── role.py               # RoleController
│   │   └── user.py               # UserController
│   ├── core/                     # 核心模块
│   │   ├── bgtask.py             # 后台任务管理
│   │   ├── crud.py               # CRUDBase 泛型基类
│   │   ├── ctx.py                # 上下文变量（CTX_USER_ID）
│   │   ├── dependency.py         # 鉴权/权限依赖注入
│   │   ├── exceptions.py         # 异常处理
│   │   ├── init_app.py           # 应用初始化（中间件、路由、数据）
│   │   └── middlewares.py        # 中间件（CORS、后台任务、审计日志）
│   ├── log/log.py                # 日志配置（Loguru）
│   ├── models/                   # 数据模型（Tortoise ORM）
│   │   ├── __init__.py           # 模型导出
│   │   ├── admin.py              # User/Role/Menu/Api/Dept/AuditLog
│   │   ├── base.py               # BaseModel/TimestampMixin
│   │   └── enums.py              # 枚举定义
│   ├── schemas/                  # Pydantic 数据校验模式
│   │   ├── apis.py               # ApiCreate/ApiUpdate
│   │   ├── base.py               # Success/Fail/SuccessExtra 响应
│   │   ├── depts.py              # DeptCreate/DeptUpdate
│   │   ├── login.py              # 登录相关 Schema
│   │   ├── menus.py              # MenuCreate/MenuUpdate/MenuType
│   │   ├── roles.py              # RoleCreate/RoleUpdate/RoleUpdateMenusApis
│   │   └── users.py              # UserCreate/UserUpdate/UpdatePassword
│   ├── settings/config.py        # 配置（Settings）
│   ├── utils/
│   │   ├── jwt_utils.py          # JWT 工具
│   │   └── password.py           # 密码工具（argon2）
│   └── __init__.py               # FastAPI 应用工厂
├── deploy/                       # 部署配置
│   ├── entrypoint.sh             # 容器入口
│   └── web.conf                  # Nginx 配置
├── web/                          # 前端应用
│   ├── src/
│   │   ├── api/index.js          # 所有后端 API 调用
│   │   ├── components/           # 通用组件
│   │   │   ├── common/           # AppProvider/AppFooter/LoadingEmptyWrapper
│   │   │   ├── icon/             # 图标组件
│   │   │   ├── page/             # CommonPage/AppPage
│   │   │   ├── query-bar/        # QueryBar 查询栏
│   │   │   └── table/            # CrudTable/CrudModal
│   │   ├── composables/useCRUD.js  # CRUD 组合式 API
│   │   ├── directives/permission.js # v-permission 权限指令
│   │   ├── layout/               # 布局组件
│   │   ├── router/               # 路由（基本路由 + 动态路由）
│   │   ├── store/                # Pinia 状态管理
│   │   │   └── modules/
│   │   │       ├── app/          # 应用全局状态
│   │   │       ├── permission/   # 权限状态（动态路由/API 权限）
│   │   │       ├── tags/         # 标签页状态
│   │   │       └── user/         # 用户状态
│   │   ├── utils/                # 工具函数
│   │   │   ├── http/             # Axios 封装（请求/响应拦截器）
│   │   │   ├── auth/             # 鉴权工具
│   │   │   └── common/           # 通用工具
│   │   └── views/                # 页面视图
│   │       ├── error-page/       # 错误页面
│   │       ├── login/            # 登录页
│   │       ├── profile/          # 个人中心
│   │       ├── system/           # 系统管理
│   │       │   ├── api/          # API 管理
│   │       │   ├── auditlog/     # 审计日志
│   │       │   ├── dept/         # 部门管理
│   │       │   ├── menu/         # 菜单管理
│   │       │   ├── role/         # 角色管理
│   │       │   └── user/         # 用户管理
│   │       └── workbench/        # 工作台
│   ├── settings/                 # 前端配置
│   └── vite.config.js
├── Dockerfile
├── Makefile
├── pyproject.toml
├── requirements.txt
├── run.py                        # 启动入口
└── uv.lock
```

---

## 核心架构模式

### 分层架构（后端）

```
┌──────────────────────────────┐
│   API 路由层 (app/api/v1/)    │  ← FastAPI Router，定义接口路径/参数
├──────────────────────────────┤
│   控制器层 (app/controllers/)  │  ← 业务逻辑，继承 CRUDBase
├──────────────────────────────┤
│   Schema 层 (app/schemas/)    │  ← Pydantic 请求/响应校验
├──────────────────────────────┤
│   模型层 (app/models/)        │  ← Tortoise ORM 模型定义
├──────────────────────────────┤
│   数据库 (SQLite/MySQL/PG)    │
└──────────────────────────────┘
```

### 统一响应格式

所有 API 响应统一使用以下三种格式之一：

```python
# 普通成功响应
Success(code=200, msg="OK", data={...})

# 错误响应
Fail(code=400, msg="错误信息")

# 分页列表响应
SuccessExtra(code=200, data=[...], total=100, page=1, page_size=10)
```

响应 JSON 结构：
```json
{"code": 200, "msg": "OK", "data": {...}}
// 分页多了 total/page/page_size
{"code": 200, "msg": "OK", "data": [...], "total": 100, "page": 1, "page_size": 10}
```

### 权限模型

```
User ──多对多──> Role ──多对多──> Menu  (菜单权限)
                 Role ──多对多──> Api   (接口权限，基于 method+path)
```

- **超级管理员** (`is_superuser=True`)：跳过所有权限检查
- **普通用户**：通过角色关联的 API 权限控制接口访问
- **菜单权限**：控制前端可见菜单项
- **按钮权限**：前端 `v-permission` 指令控制按钮显隐

---

## 后端开发指南

### 步骤 1：创建数据模型

在 `app/models/admin.py` 中添加新模型：

```python
class YourModel(BaseModel, TimestampMixin):
    name = fields.CharField(max_length=50, unique=True, description="名称", index=True)
    description = fields.CharField(max_length=200, null=True, description="描述")
    is_active = fields.BooleanField(default=True, description="是否激活", index=True)

    class Meta:
        table = "your_model"
```

**关键规则：**
- 所有模型继承 `BaseModel, TimestampMixin`（获得 `id`, `created_at`, `updated_at`）
- 字符串字段使用 `max_length`，可搜索字段加 `index=True`
- 使用 `description` 参数添加字段说明
- `Meta.table` 指定数据库表名

### 步骤 2：创建 Pydantic Schema

在 `app/schemas/` 下新建文件，定义 Create/Update Schema：

```python
# app/schemas/your_module.py
from pydantic import BaseModel, Field

class YourCreate(BaseModel):
    name: str = Field(..., description="名称", example="示例名称")
    description: str = Field("", description="描述")

class YourUpdate(BaseModel):
    id: int
    name: str = Field(..., description="名称")
    description: str = Field("", description="描述")
```

**关键规则：**
- Create Schema 不含 `id`（自增）
- Update Schema 必须包含 `id` 字段
- 使用 `Field(example=...)` 为 Swagger 文档提供示例值
- 使用 `Optional[...]` 标记可选字段

### 步骤 3：创建 Controller

在 `app/controllers/` 下新建文件，继承 `CRUDBase`：

```python
# app/controllers/your_module.py
from app.core.crud import CRUDBase
from app.models.admin import YourModel
from app.schemas.your_module import YourCreate, YourUpdate

class YourController(CRUDBase[YourModel, YourCreate, YourUpdate]):
    def __init__(self):
        super().__init__(model=YourModel)

    # 自定义业务方法
    async def get_by_name(self, name: str):
        return await self.model.filter(name=name).first()

your_controller = YourController()
```

**CRUDBase 提供的方法：**
- `get(id)` - 按 ID 获取单条
- `list(page, page_size, search=Q(), order=[])` - 分页查询
- `create(obj_in)` - 创建（接受 dict 或 pydantic model）
- `update(id, obj_in)` - 更新（使用 `exclude_unset=True, exclude={"id"}`）
- `remove(id)` - 删除

然后在 `app/controllers/__init__.py` 中导出：

```python
from .your_module import your_controller
```

### 步骤 4：创建 API 路由

在 `app/api/v1/` 下新建目录和文件：

```python
# app/api/v1/your_module/__init__.py
from fastapi import APIRouter

from .your_module import router

your_module_router = APIRouter()
your_module_router.include_router(router, tags=["模块中文名"])

__all__ = ["your_module_router"]

# app/api/v1/your_module/your_module.py
from fastapi import APIRouter, Query
from tortoise.expressions import Q
from app.controllers import your_controller
from app.schemas.base import Success, SuccessExtra
from app.schemas.your_module import *

router = APIRouter()

@router.get("/list", summary="查看列表")
async def list_items(
    page: int = Query(1, description="页码"),
    page_size: int = Query(10, description="每页数量"),
    name: str = Query("", description="名称搜索"),
):
    q = Q()
    if name:
        q &= Q(name__contains=name)
    total, objs = await your_controller.list(page=page, page_size=page_size, search=q)
    data = [await obj.to_dict() for obj in objs]
    return SuccessExtra(data=data, total=total, page=page, page_size=page_size)

@router.post("/create", summary="创建")
async def create_item(obj_in: YourCreate):
    await your_controller.create(obj_in=obj_in)
    return Success(msg="Created Successfully")

@router.post("/update", summary="更新")
async def update_item(obj_in: YourUpdate):
    await your_controller.update(id=obj_in.id, obj_in=obj_in)
    return Success(msg="Updated Successfully")

@router.delete("/delete", summary="删除")
async def delete_item(item_id: int = Query(..., description="ID")):
    await your_controller.remove(id=item_id)
    return Success(msg="Deleted Successfully")
```

**关键规则：**
- GET 请求用 `Query(...)` 接收参数
- POST 请求用 Pydantic Schema 接收 Body
- `summary` 参数会显示在 Swagger 文档中，也是审计日志的字段
- 所有读写接口都放在同一个 router 中
- 列表接口返回 `SuccessExtra`，其他返回 `Success`

### 步骤 5：注册路由

在 `app/api/v1/__init__.py` 中注册：

```python
from .your_module import your_module_router

v1_router.include_router(
    your_module_router,
    prefix="/your-module",
    dependencies=[DependPermission]  # 加入权限控制
)
```

**权限控制规则：**
- 需要鉴权的路由加 `dependencies=[DependPermission]`
- 通过 `DependPermission` 后，框架自动根据 (method, path) 匹配 API 表进行权限校验
- 公开接口（如登录）不加此依赖
- 单个接口级别也可以加 `dependencies=[DependAuth]` 只做鉴权不做 API 权限校验

### 步骤 6：初始化数据（可选）

在 `app/core/init_app.py` 的 `init_data()` 中添加种子数据（如默认菜单、默认角色权限）。

### 步骤 7：数据库迁移

```bash
# 生成迁移文件
make migrate   # 或 aerich migrate

# 应用迁移
make upgrade   # 或 aerich upgrade

# 重置数据库
make clean-db  # 删除 migrations/ 和 db.sqlite3
```

---

## 前端开发指南

> **强制规则：所有列表页面必须使用 `CrudTable` 组件。** 禁止在页面中直接使用 `NDataTable` 裸组件拼接分页、加载状态等逻辑。`CrudTable` 统一管理：后端分页、加载态、QueryBar 搜索栏、`queryItems` 双向绑定、`extraParams` 额外参数。特殊操作（如同步、清除等自定义按钮）放在 `<CommonPage>` 的 `#action` 插槽或表格上方独立操作区，`getData` 通过闭包将额外参数合并传入。

### 步骤 1：注册 API 接口

在 `web/src/api/index.js` 中添加 API 调用：

```javascript
// your-module
getYourList: (params = {}) => request.get('/your-module/list', { params }),
createYour: (data = {}) => request.post('/your-module/create', data),
updateYour: (data = {}) => request.post('/your-module/update', data),
deleteYour: (params = {}) => request.delete('/your-module/delete', { params }),
```

### 步骤 2：创建页面视图

在 `web/src/views/` 下新建模块目录和 `index.vue`：

**推荐使用 CrudTable + useCRUD 组合模式：**

```vue
<script setup>
import { h, onMounted, ref, resolveDirective, withDirectives } from 'vue'
import { NButton, NInput, NPopconfirm, NTag } from 'naive-ui'
import CommonPage from '@/components/page/CommonPage.vue'
import QueryBarItem from '@/components/query-bar/QueryBarItem.vue'
import CrudModal from '@/components/table/CrudModal.vue'
import CrudTable from '@/components/table/CrudTable.vue'
import { renderIcon } from '@/utils'
import { useCRUD } from '@/composables'
import api from '@/api'

defineOptions({ name: '模块名' })

const $table = ref(null)
const queryItems = ref({})
const vPermission = resolveDirective('permission')

const {
  modalVisible, modalTitle, modalAction, modalLoading,
  handleSave, modalForm, modalFormRef,
  handleEdit, handleDelete, handleAdd,
} = useCRUD({
  name: '模块',
  initForm: {},
  doCreate: api.createYour,
  doUpdate: api.updateYour,
  doDelete: api.deleteYour,
  refresh: () => $table.value?.handleSearch(),
})

onMounted(() => {
  $table.value?.handleSearch()
})

const columns = [
  { title: '名称', key: 'name', width: 60, align: 'center', ellipsis: { tooltip: true } },
  { title: '描述', key: 'description', width: 100, align: 'center', ellipsis: { tooltip: true } },
  {
    title: '操作', key: 'actions', width: 80, align: 'center', fixed: 'right',
    render(row) {
      return [
        withDirectives(
          h(NButton, {
            size: 'small', type: 'primary', style: 'margin-right: 8px;',
            onClick: () => handleEdit(row),
          }, { default: () => '编辑', icon: renderIcon('material-symbols:edit', { size: 16 }) }),
          [[vPermission, 'post/api/v1/your-module/update']]
        ),
        h(NPopconfirm, {
          onPositiveClick: () => handleDelete({ item_id: row.id }),
        }, {
          trigger: () =>
            withDirectives(
              h(NButton, { size: 'small', type: 'error' }, {
                default: () => '删除',
                icon: renderIcon('material-symbols:delete-outline', { size: 16 }),
              }),
              [[vPermission, 'delete/api/v1/your-module/delete']]
            ),
        }),
      ]
    },
  },
]
</script>

<template>
  <CommonPage title="模块管理">
    <template #action>
      <NButton
        v-permission="'post/api/v1/your-module/create'"
        type="primary"
        @click="handleAdd"
      >
        <TheIcon icon="material-symbols:add" :size="18" class="mr-5" />新建
      </NButton>
    </template>

    <CrudTable
      ref="$table"
      :columns="columns"
      :get-data="api.getYourList"
    />

    <CrudModal
      v-model:visible="modalVisible"
      :title="modalTitle"
      :loading="modalLoading"
      @save="handleSave"
    >
      <!-- 表单内容 -->
    </CrudModal>
  </CommonPage>
</template>
```

### 步骤 3：权限指令使用

`v-permission` 指令的值为 `{method_lower}{path}` 格式：

```html
<!-- 按钮级别权限控制 -->
<NButton v-permission="'post/api/v1/user/create'">新建</NButton>
<NButton v-permission="'delete/api/v1/user/delete'">删除</NButton>

<!-- 或在 render 函数中使用 -->
withDirectives(
  h(NButton, { ... }, { ... }),
  [[vPermission, 'post/api/v1/user/update']]
)
```

权限值格式：`METHOD + PATH`（method 小写）
- 例如 `get/api/v1/user/list`
- 例如 `post/api/v1/user/create`
- 例如 `put/api/v1/user/update`
- 例如 `delete/api/v1/user/delete`

### 步骤 4：路由注册

**动态路由（推荐）：** 在后端「菜单管理」中添加菜单即可，前端会自动从 `/api/v1/base/usermenu` 获取并生成路由。

**静态路由：** 在 `web/src/router/routes/index.js` 的 `basicRoutes` 中添加。

### 步骤 5：状态管理

| Store | 用途 |
|---|---|
| `useUserStore` | 用户信息、登录/登出 |
| `usePermissionStore` | 动态路由、API 权限列表 |
| `useAppStore` | 暗黑模式、侧边栏、语言 |
| `useTagsStore` | 标签页管理 |

---

## 完整开发流程（以"任务管理"模块为例）

### 后端

1. **创建模型** → `app/models/admin.py` 添加 `Task` 类
2. **创建 Schema** → `app/schemas/tasks.py` 添加 `TaskCreate`、`TaskUpdate`
3. **创建 Controller** → `app/controllers/task.py` 添加 `TaskController`
4. **注册 Controller** → `app/controllers/__init__.py` 导出
5. **创建 API 路由** → `app/api/v1/tasks/__init__.py`（创建 `tasks_router`）+ `app/api/v1/tasks/tasks.py`
6. **注册路由** → `app/api/v1/__init__.py` 导入 `tasks_router` 并注册（加 `DependPermission`）
7. **数据库迁移** → `make migrate && make upgrade`
8. **添加种子数据**（可选）→ `app/core/init_app.py`

### 前端

1. **注册 API 调用** → `web/src/api/index.js`
2. **创建视图页面** → `web/src/views/task/index.vue`
3. **后端菜单管理** → 添加「任务管理」菜单，路径 `/task`，组件 `/task`
4. **后端角色授权** → 给角色分配菜单和 API 权限
5. **刷新前端** → 自动加载新路由

---

## 常用模式速查

### Controller 扩展模式

```python
class YourController(CRUDBase[Model, CreateSchema, UpdateSchema]):
    def __init__(self):
        super().__init__(model=Model)

    # 按字段查询
    async def get_by_field(self, field_value):
        return await self.model.filter(field=field_value).first()

    # 检查存在性
    async def is_exist(self, name: str) -> bool:
        return await self.model.filter(name=name).exists()

    # 多对多关联操作
    async def update_relations(self, obj, related_ids):
        await obj.related_field.clear()
        for rel_id in related_ids:
            rel_obj = await RelatedModel.filter(id=rel_id).first()
            await obj.related_field.add(rel_obj)

    # 事务操作
    from tortoise.transactions import atomic
    @atomic()
    async def transactional_operation(self, ...):
        ...
```

### 树形数据模式

**菜单/部门树：** 使用 `parent_id` 自引用，递归构建 children。

**闭包表（DeptClosure）：** 用于高性能树查询，记录 ancestor/descendant/level。

### 软删除模式

```python
# 模型
is_deleted = fields.BooleanField(default=False)

# 查询时过滤
q = Q(is_deleted=False)

# 删除时标记
obj.is_deleted = True
await obj.save()
```

### 审计日志

自动记录所有带 `DependPermission` 的接口调用到 `auditlog` 表，无需手动处理。中间件自动捕获：用户、路径、方法、参数、响应、响应时间、状态码。

排除路径在 `app/core/init_app.py` 的 `HttpAuditLogMiddleware` 中配置。

---

## 配置说明

### 后端配置（`app/settings/config.py`）

| 配置项 | 说明 | 默认值 |
|---|---|---|
| `DEBUG` | 调试模式 | True |
| `SECRET_KEY` | JWT 签名密钥 | ... |
| `JWT_ALGORITHM` | JWT 算法 | HS256 |
| `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` | Token 过期时间 | 7天 |
| `TORTOISE_ORM` | 数据库配置 | SQLite |
| `DATETIME_FORMAT` | 日期格式化 | `%Y-%m-%d %H:%M:%S` |

切换数据库：修改 `TORTOISE_ORM.connections` 和 `default_connection`。

### 前端配置（`web/settings/`）

环境变量在 `.env` 中配置，通过 `vite.config.js` 的 `convertEnv` 处理。

---

## Docker 部署

```bash
# 拉取镜像
docker pull mizhexiaoxiao/vue-fastapi-admin:latest
docker run -d --restart=always --name=vue-fastapi-admin -p 9999:80 mizhexiaoxiao/vue-fastapi-admin

# 本地构建
docker build --no-cache . -t vue-fastapi-admin
docker run -d --restart=always --name=vue-fastapi-admin -p 9999:80 vue-fastapi-admin
```

容器内 Nginx 反向代理：`/api/*` → `127.0.0.1:9999`，其他请求 → `/web/dist/`。

---

## 开发注意事项

1. **模型导出**：新模型必须在 `app/models/__init__.py` 中导入（`from .admin import *` 已覆盖 `admin.py` 中的所有类）
2. **Controller 导出**：新控制器必须在 `app/controllers/__init__.py` 中导出
3. **Schema 响应**：列表用 `SuccessExtra`，单条操作用 `Success`，错误用 `Fail`
4. **审计日志**：`summary` 参数会显示在审计日志的"接口描述"列，建议使用中文
5. **前端 API 调用**：统一通过 `web/src/api/index.js` 的 `request` 实例，自动附加 token, 处理同步等时间较长的请求时，增加 `{ timeout: 0 }` 配置
6. **权限指令**：`v-permission` 值格式为 `method+path`（method 小写），在 JSX/render 中使用 `withDirectives`
7. **API 子模块 `__init__.py`**：每个 `app/api/v1/xxx/__init__.py` 必须创建 `xxx_router = APIRouter()` 并 `include_router(router, tags=[...])`，不可留空，否则 `v1/__init__.py` 导入时报错
8. **禁用旧模块**：删除不需要的菜单、API 权限、角色关联即可，模型可保留
9. **密码安全**：使用 `app/utils/password.py` 的 `get_password_hash` / `verify_password`，不要直接存储明文

---

## 常见踩坑与解决方案

### 中间件与 Multipart 上传

`HttpAuditLogMiddleware` 的 `dispatch()` 方法**无条件**调用 `before_request()`，而 `before_request()` 中会执行 `await request.form()` 解析请求体。对于 multipart 文件上传，二进制文件内容会被解析并可能触发 `UnicodeDecodeError: 'latin-1' codec can't encode characters`。

**修复**：`dispatch()` 中增加排除检查，跳过 `before_request()` 的请求体解析。同时所有上传/导出接口路径加入 `exclude_paths`：

```python
# app/core/middlewares.py
def _is_excluded(self, request: Request) -> bool:
    for path in self.exclude_paths:
        if re.search(path, request.url.path, re.I) is not None:
            return True
    return False

async def dispatch(self, request, call_next):
    if not self._is_excluded(request):
        await self.before_request(request)
    ...
```

```python
# app/core/init_app.py
exclude_paths=[
    "/api/v1/base/access_token",
    "/api/v1/skill/export",
    "/api/v1/workspace/sheet/upload",
    "/api/v1/workspace/sheet/export",
    "/api/v1/workspace/analysis/export",
    "/docs", "/openapi.json",
],
```

### AI 代理异步调用（openai SDK）

openai SDK（`client.chat.completions.create()`）是同步阻塞调用。在 async 函数中直接使用会阻塞 FastAPI 事件循环，导致其他用户请求卡住。

**必须使用 `asyncio.to_thread()` 将同步调用放到线程池**：

```python
async def _call_ai(client, model, system_prompt, user_prompt):
    def _sync_call():
        response = client.chat.completions.create(
            model=model,
            messages=[...],
            temperature=0.7,
        )
        return response.choices[0].message.content
    return await asyncio.to_thread(_sync_call)
```

### Tortoise ORM 不能在同步线程中调用

Tortoise ORM 的所有操作（`.get()`, `.filter()`, `.create()` 等）必须在事件循环中 `await`。**严禁**在 `asyncio.to_thread()` 或 `run_in_executor()` 的回调中调用 Tortoise ORM。

错误示例（会静默失败或报 RuntimeError）：
```python
# ❌ 在线程池中调用 Tortoise ORM
def _read():
    s = OriginalSheet.get(id=sid)  # 报错或被 except: pass 吞掉
return await asyncio.to_thread(_read)
```

正确做法：先用 `await asyncio.gather(*tasks)` 异步查询记录，再对 pandas 等同步 I/O 使用 `asyncio.to_thread()`：
```python
# ✅ 先异步查询，再线程池读文件
records = await asyncio.gather(*[OriginalSheet.get_or_none(id=sid) for sid in sheet_ids])
def _read_excel(rec):
    return pd.read_excel(rec.file_path)
for rec in records:
    result = await asyncio.to_thread(_read_excel, rec)
```

### NModal preset="card" 按钮不显示

Naive UI 的 `NModal preset="card"` 模式下，必须显式设置 `positive-text` / `negative-text`，或使用 `#footer` 插槽手动放置按钮。

**推荐使用 `#footer` 插槽**，可靠且可控：
```html
<NModal v-model:show="show" title="标题" preset="card">
  <NForm>...</NForm>
  <template #footer>
    <NSpace justify="end">
      <NButton @click="show = false">取消</NButton>
      <NButton type="primary" @click="submit">确认</NButton>
    </NSpace>
  </template>
</NModal>
```

### CrudModal + useCRUD 保存按钮无回调

`useCRUD` 的 `handleSave` 依赖 `modalFormRef.value?.validate()`，必须在 CrudModal 内包裹 `<NForm ref="modalFormRef">`，否则 `validate` 为 undefined，保存逻辑静默跳过。

### CodeMirror 编辑器高度问题

CodeMirror 的 `.CodeMirror` 外层 div 不会自动填充父容器。需要双重保障：

```javascript
// JS: 初始化后设置
cmInstance.getWrapperElement().style.height = '100%'
```

```css
/* CSS: 全局覆盖 */
.CodeMirror { height: 100% !important; }
```

### 前端 JS/CSS 库本地化

所有外部 CDN 库统一下载到 `web/public/lib/`，在 `index.html` 中引用本地路径：

```
web/public/lib/
├── vditor/index.css, index.min.js
└── codemirror/codemirror.min.css, .js, dracula.min.css,
              htmlmixed.min.js, xml.min.js, javascript.min.js, css.min.js
```

### Controller 不使用 CRUDBase 时的模式

对于复杂模块（如统计中心的 ReportService），可以不继承 CRUDBase，直接创建独立 Service 类，手动管理 Tortoise ORM 操作。路由中通过权限检查（`workspace_controller.check_permission`）确保安全性。

### 10. **文件上传**：使用 `UploadFile = File(...)` + `multipart/form-data`，限制格式用 `file.filename.endswith(...)`
11. **文件下载/导出**：使用 `FileResponse(filepath, filename=...)` 或 `Response(content=bytes, media_type=...)`，中文文件名需 `urllib.parse.quote` 编码
12. **M2M 关联权限**：模型中使用 `ManyToManyField("models.User")`，Controller 中提供 `update_users(obj, user_ids)` 方法清空并重建关联
13. **异步 AI 调用**：所有 openai SDK 调用必须包在 `asyncio.to_thread()` 中，防止阻塞事件循环
14. **Tortoise ORM 线程安全**：Tortoise 操作只能在 async 上下文中 `await`，禁止在线程池/executor 中调用
15. **中间件排除**：文件上传、导出等二进制接口路径必须加入 `HttpAuditLogMiddleware.exclude_paths`

## 已实现模块速查

| 模块 | 路由前缀 | 模型 | 特点 |
|---|---|---|---|
| Skill 管理 | `/skill` | Skill (title, content, users M2M) | vditor 所见即所得编辑器 |
| AI 代理管理 | `/ai-proxy` | AIProxy (name, url, token, model, users M2M) | 标准 CrudTable 页面 |
| 数据工作台 | `/workspace` | Workspace → 多数据源 (Excel/文档/数据库/静态文件) | 左侧工作区 + 右侧 NTabs 多数据源，卡片式布局 |
| 统计中心（报告生成） | `/report` | Report (workspace FK, content HTML) | CodeMirror 编辑 → PDF/Word/HTML 导出 |
| 路网数据中心 | `/region` | Region 自引用树 + RegionBoundary + RoadNetwork | NTree 双面板 + OSMnx 下载 |
| 路网工作台 | `/region/road-network` | RoadNetwork 瓦片预览 + 边数据编辑 | Leaflet 多底图 + 瓦片叠加 + 图层导出 + AI/CV 处理 |
| 路网素材 | `/region/road-material` | RoadMaterial (图片+EXIF+短链接) | 上传/编辑/删除 + AI/CV 处理 + 预览工作区（缩放旋转+GPS地图） |

### 前端库本地化

| 库 | 路径 | 用途 |
|---|---|---|
| Leaflet 1.9.4 | `web/public/lib/leaflet/` | 地图渲染 (CSS/JS/marker 图标) |
| html-to-image 1.11.11 | `web/public/lib/html-to-image/` | DOM → Canvas/PNG 截取（图层导出） |
| Vditor | `web/public/lib/vditor/` | Markdown 所见即所得编辑器 |
| CodeMirror | `web/public/lib/codemirror/` | 代码/HTML 编辑器 |

### UnoCSS 字体注意事项

全局 `html { font-size: 4px }` 使 1rem=4px，UnoCSS 的 `text-*` 类（rem）全部缩到 1/4。新建页面时**必须在 `<style scoped>` 中用 `!important` + px 覆盖 `text-xs` 到 `text-xl` 的 `font-size` 和 `line-height`**，禁止直接改全局 `html` 基准。
