# Vue-FastAPI-Admin (VFA) 开发核心规则
## 一、后端核心规范

### 1.1 分层架构（强制）

```
API 路由层 (app/api/v1/)   → 仅处理请求参数、响应格式，不写业务逻辑
控制器层 (app/controllers/) → 继承 CRUDBase，实现业务逻辑
Schema 层 (app/schemas/)   → Pydantic 模型，请求/响应校验
模型层 (app/models/)       → Tortoise ORM 模型定义
```

**规则：**
- 控制器 **必须** 继承 `CRUDBase[Model, CreateSchema, UpdateSchema]`，除非特殊场景（如复杂报表）
- 路由函数 **禁止** 直接操作 ORM，所有数据库调用必须通过控制器
- 每个路由函数的 `summary` 参数必须填写中文描述（会写入审计日志）

### 1.2 CRUDBase 使用规范

```python
class YourController(CRUDBase[YourModel, YourCreate, YourUpdate]):
    def __init__(self):
        super().__init__(model=YourModel)

    # 自定义查询方法
    async def get_by_name(self, name: str):
        return await self.model.filter(name=name).first()

    # 存在性检查
    async def is_exist(self, name: str) -> bool:
        return await self.model.filter(name=name).exists()

    # 多对多关联更新（清空 + 重建）
    async def update_relations(self, obj, related_ids):
        await obj.related_field.clear()
        for rid in related_ids:
            rel = await RelatedModel.filter(id=rid).first()
            if rel:
                await obj.related_field.add(rel)

    # 事务操作（装饰器）
    from tortoise.transactions import atomic
    @atomic()
    async def transactional_operation(self, ...):
        ...
```

### 1.3 统一响应格式（强制）

```python
# 普通成功
return Success(data={"id": 1})          # {"code":200,"msg":"OK","data":{...}}
# 分页列表
return SuccessExtra(data=list_obj, total=100, page=1, page_size=10)
# 错误
return Fail(code=400, msg="参数错误")
```

**禁止** 直接返回 dict 或自定义格式。

### 1.4 数据库模型规范

```python
class YourModel(BaseModel, TimestampMixin):
    name = fields.CharField(max_length=50, unique=True, description="名称", index=True)
    is_active = fields.BooleanField(default=True, description="是否激活", index=True)

    class Meta:
        table = "your_model"
```

- 所有模型必须继承 `BaseModel, TimestampMixin`（自动获得 `id`, `created_at`, `updated_at`）
- 字符串字段必须指定 `max_length`
- 用于搜索/过滤的字段加 `index=True`
- `description` 必填，用于生成文档
- `Meta.table` 显式指定表名

### 1.5 API 路由注册模式

```python
# app/api/v1/your_module/__init__.py
from fastapi import APIRouter
from .your_module import router

your_module_router = APIRouter()
your_module_router.include_router(router, tags=["模块中文名"])
__all__ = ["your_module_router"]

# app/api/v1/__init__.py
from .your_module import your_module_router
v1_router.include_router(
    your_module_router,
    prefix="/your-module",
    dependencies=[DependPermission]      # 需要权限控制
)
```

**注意：** 每个子模块的 `__init__.py` **不能为空**，必须创建 `xxx_router` 并 include 实际路由。

### 1.6 路由函数参数规范

```python
@router.get("/list")
async def list_items(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(10, ge=1, le=100, description="每页数量"),
    name: str = Query("", description="名称搜索"),
):
    q = Q()
    if name:
        q &= Q(name__contains=name)
    ...

@router.post("/create")
async def create_item(obj_in: YourCreate):   # 使用 Pydantic schema
    ...

@router.delete("/delete")
async def delete_item(item_id: int = Query(..., description="ID")):
    ...
```

- GET 请求用 `Query(...)`，POST/PUT 用 Body schema
- 所有参数必须有 `description`
- 分页参数添加 `ge=1, le=...` 校验

---

## 二、前端核心规范

### 2.1 CrudTable 强制使用（重要）

> **所有列表页面必须使用 `CrudTable` 组件**，禁止直接使用 `NDataTable` + 手动分页/加载态。

**正确用法：**

```vue
<template>
  <CommonPage title="模块管理">
    <template #action>
      <NButton @click="handleAdd">新建</NButton>
    </template>

    <CrudTable
      ref="$table"
      :columns="columns"
      :get-data="api.getYourList"
    />
  </CommonPage>
</template>

<script setup>
import { useCRUD } from '@/composables'
import CrudTable from '@/components/table/CrudTable.vue'

const $table = ref(null)
const { handleAdd, handleEdit, handleDelete } = useCRUD({
  name: '模块',
  doCreate: api.createYour,
  doUpdate: api.updateYour,
  doDelete: api.deleteYour,
  refresh: () => $table.value?.handleSearch(),
})
</script>
```

**为什么必须使用 CrudTable？**
- 统一管理后端分页、加载状态、搜索栏（`QueryBar`）
- 自动处理 `queryItems` 双向绑定和 `extraParams`
- 减少重复代码，保证交互一致性

### 2.2 权限指令 v-permission

```html
<!-- 模板中使用 -->
<NButton v-permission="'post/api/v1/user/create'">新建</NButton>

<!-- render 函数中使用 -->
import { withDirectives, resolveDirective } from 'vue'
const vPermission = resolveDirective('permission')
withDirectives(
  h(NButton, { onClick: handleEdit }),
  [[vPermission, 'post/api/v1/user/update']]
)
```

**权限值格式：** `{method_lowercase}{path}`
- 示例：`get/api/v1/user/list`、`post/api/v1/user/create`、`delete/api/v1/user/delete`

### 2.3 useCRUD 组合式函数规范

```javascript
const {
  modalVisible,      // 弹窗显隐
  modalTitle,        // 弹窗标题（自动设置"新建/编辑"）
  modalAction,       // 'create' 或 'update'
  modalLoading,      // 保存按钮加载态
  handleSave,        // 保存方法（自动校验 modalFormRef）
  modalFormRef,      // 必须绑定到 NForm 的 ref
  handleEdit,        // 编辑（自动填充表单）
  handleDelete,      // 删除（需传入参数）
  handleAdd,         // 新增
} = useCRUD({
  name: '模块',
  initForm: { name: '', description: '' },   // 表单初始值
  doCreate: api.createYour,
  doUpdate: api.updateYour,
  doDelete: api.deleteYour,
  refresh: () => $table.value?.handleSearch(),
})
```

**关键：** 模板中必须在 `CrudModal` 内包裹 `<NForm ref="modalFormRef">`，否则 `handleSave` 不会执行。

### 2.4 NTree 使用规范（树形数据）

```vue
<NTree
  :data="treeData"
  :pattern="searchPattern"
  :filter="(pattern, node) => !pattern || node.label.toLowerCase().includes(pattern.toLowerCase())"
  virtual-scroll
  @update:selected-keys="onSelect"
/>

<script>
// 重要：@update:selected-keys 的第二个参数是选中节点数组，不是单对象
function onSelect(keys, option) {
  const node = Array.isArray(option) ? option[0] : option
  if (!node) return
  console.log(node.id, node.label)
}
</script>
```

**规则：**
- 必须加 `virtual-scroll` 避免大量节点卡顿
- 搜索框绑定 `:pattern` + `:filter`，Naive UI 自动展开匹配路径
- 长文本节点需要 CSS 截断（见 2.6）

### 2.5 双面板布局防溢出（重要）

当页面包含左右两个面板（如树 + 详情）时，**必须**使用 flex 布局 + 溢出控制：

```html
<div class="dual-panel-layout">
  <NCard class="left-panel">...</NCard>
  <NCard class="right-panel">...</NCard>
</div>
```

```css
.dual-panel-layout {
  display: flex;
  height: calc(100vh - 180px);   /* 固定高度，根据页面调整 */
  overflow: hidden;
  gap: 8px;
}
.left-panel {
  width: 320px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.right-panel {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
/* 穿透 NCard 内容区 */
.left-panel :deep(.n-card__content),
.right-panel :deep(.n-card__content) {
  flex: 1;
  min-height: 0;
  overflow: auto;
}
/* 树节点文本截断 */
.left-panel :deep(.n-tree-node-content__text) {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
```

**禁止** 使用 `NSpace` 作为外层容器（它不传递高度约束）。

### 2.6 NModal preset="card" 按钮不显示问题

必须使用 `#footer` 插槽手动放置按钮：

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

### 2.7 文件下载的 Blob 响应拦截

在 `web/src/utils/http/index.js` 中，响应拦截器必须处理 Blob：

```javascript
// 响应拦截器
instance.interceptors.response.use(
  (response) => {
    const { config, data } = response
    // 如果是 blob 响应，直接透传
    if (config.responseType === 'blob' || data instanceof Blob) {
      return Promise.resolve(response)
    }
    // 正常 JSON 处理
    if (data?.code !== 200) {
      return Promise.reject(new Error(data.msg || '请求失败'))
    }
    return data
  },
  (error) => Promise.reject(error)
)
```

否则后端返回的 `FileResponse` 会被误判为错误响应导致下载失败。

---

## 三、异步与并发规范

### 3.1 同步阻塞操作必须放入线程池

FastAPI 是异步框架，**任何 CPU 密集型或同步 I/O 操作都会阻塞事件循环**，导致所有请求卡死。

**必须使用 `asyncio.to_thread()` 或 `run_in_executor()`：**

```python
import asyncio

async def blocking_operation():
    def _sync_blocking():
        # 例如：pandas.read_excel(), osmnx.graph_from_place(), openai.ChatCompletion.create()
        return result
    return await asyncio.to_thread(_sync_blocking)
```

**典型场景：**
- OSMnx 路网下载
- pandas 读写 Excel/CSV
- openai 同步 SDK 调用
- 大文件 I/O

### 3.2 Tortoise ORM 的线程安全（关键）

**严禁**在线程池回调中调用 Tortoise ORM 的任何方法（`.get()`, `.filter()`, `.create()` 等）。Tortoise 必须在事件循环中 `await`。

```python
# ❌ 错误：在线程中调用 ORM
def _bad():
    user = User.get(id=1)   # 会报错或被吞掉
await asyncio.to_thread(_bad)

# ✅ 正确：先异步查询，再线程池处理其他事
user = await User.get(id=1)
def _process_data():
    # 只做非 ORM 操作，例如 pandas 处理
    df = pd.DataFrame(user.data)
    return df.to_dict()
result = await asyncio.to_thread(_process_data)
```

### 3.3 耗时 API 的超时设置

前端调用可能长时间阻塞的接口（如导入、清空、下载大文件）时，必须设置 `timeout: 0`：

```javascript
api.importRegions: () => request.post('/region/import', {}, { timeout: 0 })
api.clearRegions: () => request.post('/region/clear', {}, { timeout: 0 })
```

后端中间件默认超时约 12 秒，超时 0 表示无限等待。

---

## 四、中间件与异常处理

### 4.1 审计日志中间件排除路径

`HttpAuditLogMiddleware` 会解析请求体。对于文件上传、导出等二进制接口，解析 `multipart/form-data` 会触发编码错误。**必须**在 `init_app.py` 中配置排除路径：

```python
exclude_paths = [
    "/api/v1/base/access_token",
    "/api/v1/your-module/upload",
    "/api/v1/your-module/export",
    "/docs", "/openapi.json",
]
```

### 4.2 自定义异常处理

```python
# app/core/exceptions.py
from fastapi import HTTPException

class BusinessError(Exception):
    def __init__(self, code: int, msg: str):
        self.code = code
        self.msg = msg

# 在路由中抛出
raise BusinessError(400, "数据已存在")
```

全局异常捕获会统一返回 `Fail` 格式。

---

## 五、数据库迁移

```bash
# 生成迁移文件
make migrate       # 或 aerich migrate

# 应用迁移
make upgrade       # 或 aerich upgrade

# 重置数据库（删除所有表和迁移记录）
make clean-db      # 删除 migrations/ 和 db.sqlite3
```

**注意：** 每次修改模型后必须执行迁移，且迁移文件应提交到版本控制。

---

## 六、安全与密码

```python
from app.utils.password import get_password_hash, verify_password

# 创建用户时
hashed = get_password_hash(plain_password)

# 验证登录
if verify_password(plain, hashed):
    ...
```

- 禁止明文存储密码
- 使用 argon2 (passlib) 加密

---

## 七、常见错误与解决方案速查表

| 错误现象 | 原因 | 解决方案 |
|---|---|---|
| 树节点选中报 422 | `@update:selected-keys` 回调拿 `option.id` 但 `option` 是数组 | 取 `option[0].id` |
| 页面右侧内容溢出 | 使用了 `NSpace` 或未设置 `overflow: hidden` | 参考 2.5 双面板布局 |
| 上传文件时报 `UnicodeDecodeError` | 审计日志中间件解析了 `multipart` 请求体 | 将上传路径加入 `exclude_paths` |
| 前端请求长时间等待后超时 | 未设置 `timeout: 0` | 添加 `{ timeout: 0 }` |
| 异步接口卡死所有请求 | 同步阻塞操作未放入线程池 | 使用 `asyncio.to_thread()` |
| Tortoise ORM 在线程中报错 | 线程中调用了 ORM | 先 `await` 查询，再线程池处理 |
| `CrudModal` 保存无反应 | 缺少 `<NForm ref="modalFormRef">` | 添加 ref 绑定 |
| `NModal` 按钮不显示 | `preset="card"` 未用 footer 插槽 | 使用 `#footer` 插槽 |
| 文件下载返回 HTML 而非文件 | Blob 响应被拦截器错误处理 | 参考 2.7 修改拦截器 |
| 菜单树不显示 | 后端返回的 `children` 字段不是 `children` | 确保树数据字段名为 `children` |
| `import.meta.env` 在模板中报错 | Vue 模板不支持直接使用 | 在 `<script>` 中用 `computed` 定义再传递 |

---

## 八、开发流程速查（新模块）

1. **后端模型** → `app/models/admin.py`
2. **Schema** → `app/schemas/xxx.py`
3. **Controller** → `app/controllers/xxx.py`（继承 CRUDBase）
4. **导出 Controller** → `app/controllers/__init__.py`
5. **API 路由** → `app/api/v1/xxx/__init__.py` + `xxx.py`
6. **注册路由** → `app/api/v1/__init__.py`（加 `DependPermission`）
7. **数据库迁移** → `make migrate && make upgrade`
8. **前端 API** → `web/src/api/index.js`
9. **前端页面** → `web/src/views/xxx/index.vue`（必须用 `CrudTable` + `useCRUD`）
10. **菜单配置** → 后台「菜单管理」添加菜单（路径 `/xxx`，组件 `/xxx`）
11. **权限分配** → 后台「角色管理」分配菜单和 API 权限

---

## 九、强制规则汇总

1. **后端**：所有控制器继承 `CRUDBase`，所有路由加 `summary` 中文描述
2. **前端**：所有列表页必须用 `CrudTable`，禁止手写 `NDataTable` + 分页
3. **双面板**：必须用 flex + `overflow: hidden`，禁止用 `NSpace`
4. **树组件**：必须加 `virtual-scroll`，`@update:selected-keys` 回调取 `option[0]`
5. **异步**：同步阻塞操作必须 `asyncio.to_thread()`，Tortoise ORM 禁止在线程池调用
6. **超时**：耗时后端接口前端设 `timeout: 0`，并加入审计中间件排除列表
7. **权限**：前端按钮用 `v-permission`，值为 `method+path`
8. **响应**：统一使用 `Success` / `SuccessExtra` / `Fail`
9. **文件下载**：axios 拦截器必须处理 Blob 类型
10. **数据库**：模型必须带 `description` 和 `index`（需要搜索的字段）

---

请持续更新迭代此Skill, 但请注意以下事项：
1. 此Skill模块焦于**可复用的编程规范、架构模式、避坑指南**，不包含特定业务模块的实现细节。
2. 适用于前后端开发。
3. 具体的大模块，请单独生成模块后续功能新增及迭代Skill，客户的修改涉及到该模块时再加载Skill熟悉模块