# Project Instructions

此文件整合了 `.codewhale/skills/` 下三个指导文档的核心规范，用于替代单独加载 SKILL.md 文件，减少请求量。

## Project Type: Python

### Commands
- Install: `pip install -e .`
- Test: `pytest`
- Format: `black .`
- Lint: `ruff check .`
- Database migrate: `make migrate` (aerich migrate)
- Database upgrade: `make upgrade` (aerich upgrade)
- Database reset: `make clean-db` (删除 migrations/ 和 db.sqlite3)

### Documentation
See README.md for project overview.

### Version Control
This project uses Git. See .gitignore for excluded files.

---

## 架构概览

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
| CSS 方案 | UnoCSS | - |
| 包管理 | pnpm | - |

### 分层架构（后端）

```
API 路由层 (app/api/v1/)   → FastAPI Router，仅处理请求参数/响应格式
控制器层 (app/controllers/) → 继承 CRUDBase，实现业务逻辑
Schema 层 (app/schemas/)   → Pydantic 请求/响应校验
模型层 (app/models/)       → Tortoise ORM 模型定义
数据库 (SQLite/MySQL/PG)   → Aerich 管理迁移
```

**规则：**
- 控制器 **必须** 继承 `CRUDBase[Model, CreateSchema, UpdateSchema]`，除非特殊场景（如复杂报表）
- 路由函数 **禁止** 直接操作 ORM，所有数据库调用必须通过控制器
- 每个路由函数的 `summary` 参数必须填写中文描述（会写入审计日志）

### 统一响应格式

```python
Success(data={"id": 1})              # {"code":200,"msg":"OK","data":{...}}
SuccessExtra(data=list_obj, total=100, page=1, page_size=10)  # 分页
Fail(code=400, msg="参数错误")        # 错误
```

**禁止** 直接返回 dict 或自定义格式。

### 权限模型

```
User ──多对多──> Role ──多对多──> Menu (菜单权限)
                  Role ──多对多──> Api  (接口权限，基于 method+path)
```

- **超级管理员** (`is_superuser=True`)：跳过所有权限检查
- **普通用户**：通过角色关联的 API 权限控制接口访问
- **按钮权限**：前端 `v-permission` 指令控制按钮显隐，值格式 `{method_lowercase}{path}`（如 `post/api/v1/user/create`）

---

## 后端开发规范

### CRUDBase 使用规范

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

your_controller = YourController()
```

**CRUDBase 提供的方法：** `get(id)`, `list(page, page_size, search=Q(), order=[])`, `create(obj_in)`, `update(id, obj_in)`, `remove(id)`

### 数据库模型规范

```python
class YourModel(BaseModel, TimestampMixin):
    name = fields.CharField(max_length=50, unique=True, description="名称", index=True)
    is_active = fields.BooleanField(default=True, description="是否激活", index=True)
    class Meta:
        table = "your_model"
```

- 所有模型继承 `BaseModel, TimestampMixin`（自动获得 `id`, `created_at`, `updated_at`）
- 字符串字段必须指定 `max_length`，可搜索字段加 `index=True`，`description` 必填
- `Meta.table` 显式指定表名
- 新模型必须在 `app/models/__init__.py` 中导入

### Schema 规范

```python
class YourCreate(BaseModel):
    name: str = Field(..., description="名称", example="示例名称")

class YourUpdate(BaseModel):
    id: int
    name: str = Field(..., description="名称")
```
- Create Schema 不含 `id`（自增），Update Schema 必须包含 `id`
- 使用 `Field(example=...)` 为 Swagger 文档提供示例值

### API 路由注册模式

```
app/api/v1/your_module/__init__.py   → 创建 your_module_router 并 include 实际路由（不能为空）
app/api/v1/your_module/your_module.py → 定义 router，内包含 list/create/update/delete 接口
app/api/v1/__init__.py                → include your_module_router，加 prefix + DependPermission
```

**路由函数参数规范：**
- GET 请求用 `Query(...)`，POST/PUT 用 Pydantic Schema Body
- `summary` 必填（写入审计日志的"接口描述"）
- 分页参数加 `ge=1, le=...` 校验
- 所有参数必须有 `description`

**权限控制：**
- 需要鉴权的路由加 `dependencies=[DependPermission]`
- 公开接口（如登录）不加此依赖
- 单接口级别可加 `dependencies=[DependAuth]` 只做鉴权不做 API 权限校验

### 中间件注意事项

`HttpAuditLogMiddleware` 会解析请求体，对于文件上传/导出等二进制接口，必须配置排除路径：

```python
# app/core/init_app.py 中配置
exclude_paths = [
    "/api/v1/base/access_token",
    "/api/v1/your-module/upload",
    "/api/v1/your-module/export",
    "/docs", "/openapi.json",
]
```

### 安全与密码

- 使用 `app/utils/password.py` 的 `get_password_hash` / `verify_password`
- 禁止明文存储密码，使用 argon2 (passlib) 加密

---

## 前端开发规范

### CrudTable 强制使用

> **所有列表页面必须使用 `CrudTable` 组件**，禁止直接使用 `NDataTable` + 手动分页/加载态。

`CrudTable` 统一管理：后端分页、加载态、QueryBar 搜索栏、`queryItems` 双向绑定、`extraParams`。

```vue
<template>
  <CommonPage title="模块管理">
    <template #action>
      <NButton @click="handleAdd">新建</NButton>
    </template>
    <CrudTable ref="$table" :columns="columns" :get-data="api.getYourList" />
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

### useCRUD 组合式函数

```javascript
const {
  modalVisible, modalTitle, modalAction, modalLoading,
  handleSave, modalFormRef, handleEdit, handleDelete, handleAdd,
} = useCRUD({
  name: '模块',
  initForm: { name: '', description: '' },
  doCreate: api.createYour,
  doUpdate: api.updateYour,
  doDelete: api.deleteYour,
  refresh: () => $table.value?.handleSearch(),
})
```

**关键：** 模板中必须在 `CrudModal` 内包裹 `<NForm ref="modalFormRef">`，否则 `handleSave` 不执行。

### 权限指令 v-permission

```html
<!-- 模板 -->
<NButton v-permission="'post/api/v1/user/create'">新建</NButton>
```
```javascript
// render 函数
import { withDirectives, resolveDirective } from 'vue'
const vPermission = resolveDirective('permission')
withDirectives(h(NButton, { onClick: handleEdit }), [[vPermission, 'post/api/v1/user/update']])
```

### 双面板布局防溢出（树 + 详情）

**必须**使用 flex 布局 + 溢出控制，**禁止**使用 `NSpace` 作为外层容器：

```html
<div class="dual-panel-layout">
  <NCard class="left-panel">...</NCard>
  <NCard class="right-panel">...</NCard>
</div>
```

```css
.dual-panel-layout {
  display: flex;
  height: calc(100vh - 180px);
  overflow: hidden;
  gap: 8px;
}
.left-panel { width: 320px; flex-shrink: 0; display: flex; flex-direction: column; overflow: hidden; }
.right-panel { flex: 1; min-width: 0; display: flex; flex-direction: column; overflow: hidden; }
.left-panel :deep(.n-card__content),
.right-panel :deep(.n-card__content) {
  flex: 1; min-height: 0; overflow: auto;
}
.left-panel :deep(.n-tree-node-content__text) {
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
```

### Tab 内容区滚动 — flex 布局链约束（关键）

在 Naive UI 的 `NTabs` + `NTabPane` 内部使用 flex 列布局时，必须**整条链**每个节点都满足：

1. **成为 flex 容器**：`display: flex; flex-direction: column`
2. **允许收缩**：`min-height: 0`
3. **阻断溢出传播**：`overflow: hidden`

链的每一层必须同时具备这三项，缺一即断——内容溢出会推动父容器膨胀，`overflow: auto` 失效。

**完整链模板**：
```
.n-tab-pane           { display:flex; flex-direction:column; flex:1; min-height:0; overflow:hidden }
  └── Tab 根 div       { flex-1 flex flex-col; min-height:0; overflow:hidden }  ← 每个 Tab 组件
       ├── 工具栏/上传区  (固定高度)
       └── 内容区        { flex-1; overflow:auto; min-height:0 }                ← 实际滚动的元素
```

**Naive UI 容器穿透**：`.n-tab-pane` 默认 `display:block`，必须用 `:deep()` 覆盖；`.n-spin-container` 默认无 flex 约束，必须补 `flex:1; min-height:0; overflow:hidden`。

**双栏变体**：在列 flex 内嵌行 flex 双栏时，双栏容器和左右栏均需 `min-height:0; overflow:hidden`。

**验证方法**：Playwright 注入 50 行数据后，检查滚动容器的 `clientHeight` 是否稳定（ΔCH=0），确认 `scrollTop` 可控且能滚动到底。

### NTree 使用规范

- 必须加 `virtual-scroll` 避免大量节点卡顿
- `@update:selected-keys` 的第二个参数 `option` 是**数组**，必须取 `option[0]` 才能拿到实际节点
- 搜索框绑定 `:pattern` + `:filter`，Naive UI 自动展开匹配路径

### 级联列表模式（替代 NTree 的多层级选择）

当需要逐层深入选择（国家 → 行政区 → 城市）时，使用**面包屑 + 单区域列表**模式，**禁止**使用 NDataTable + virtual-scroll + row-props 组合（虚拟滚动与 flex-height 冲突、row-props 的 onClick 在虚拟滚动下不可靠）。

```html
<!-- 面包屑导航 -->
<NBreadcrumb>
  <NBreadcrumbItem><span @click="backToLevel(0)">根</span></NBreadcrumbItem>
  <NBreadcrumbItem v-for="(item, idx) in breadcrumb" :key="item.id">
    <span v-if="idx < breadcrumb.length - 1" @click="backToLevel(idx + 1)">{{ item.name }}</span>
    <span v-else>{{ item.name }}</span>
  </NBreadcrumbItem>
</NBreadcrumb>
<!-- 列表：v-for，不用 NDataTable -->
<div class="region-list">
  <div v-for="row in filteredList" :key="row.id" @click="onClickRow(row)">...</div>
</div>
```

```javascript
const breadcrumb = ref([])
function onClickRow(row) {
  breadcrumb.value.push({ id: row.id, name: row.name })
  loadDetail(row.id)
  loadCurrentLevel()
}
function backToLevel(index) {
  breadcrumb.value = breadcrumb.value.slice(0, index)
  loadCurrentLevel()
}
```

**keepAlive 注意：** 子路由通常不设 `keepAlive: true`，`onMounted` 即足够，不依赖 `onActivated`。

### NModal preset="card" 按钮不显示

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

### 文件下载的 Blob 响应拦截

axios 响应拦截器必须处理 Blob（否则 `data?.code !== 200` 会将 Blob 误判为错误）：

```javascript
instance.interceptors.response.use(
  (response) => {
    const { config, data } = response
    if (config.responseType === 'blob' || data instanceof Blob) {
      return Promise.resolve(response)
    }
    if (data?.code !== 200) {
      return Promise.reject(new Error(data.msg || '请求失败'))
    }
    return data
  },
  (error) => Promise.reject(error)
)
```

### CodeMirror 编辑器高度问题

CodeMirror 的 `.CodeMirror` 外层 div 不自动填充父容器，需双重保障：

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
- `web/public/lib/vditor/`
- `web/public/lib/codemirror/`

### CrudTable 进阶功能

#### `rowClickSelect` — 行点击单选

`CrudTable` 支持 `row-click-select` prop，开启后点击表格行的任意非交互区域（非 checkbox / 按钮 / 开关等），自动单选该行并取消所有其他选中行。再次点击已选中行则取消选中。适用于单选场景（如弹窗中选择一条记录）。

```html
<CrudTable
  :columns="[{ type: 'selection' }, ...]"
  :get-data="api.getList"
  row-click-select
  @on-checked="(keys) => { selected = keys }"
/>
```

**交互元素过滤**：点击以下元素**不会**触发行选中（通过 `closest()` 过滤）：
- `button`, `a`, `.n-button`, `.n-switch`, `.n-tag`, `input`, `select`, `textarea`, `[role="button"]`
- selection 列单元格（`.n-data-table-td--selection`）—— 即 checkbox 本身保持原生多选行为

**注意**：`rowClickSelect` 开启时会绑定 `:checked-row-keys` 使 NDataTable 成为受控组件（编程式修改选中态可反映到 UI）。仅在 `rowClickSelect` 启用时激活，不影响默认行为。

#### `rowKey` prop 使用约束

`CrudTable` 的 `row-key` prop 类型为 **String**（属性名），**不接受函数**。错误用法：

```html
<!-- ❌ 错误：传函数会被 Vue 强转为字符串，导致所有行 key 为 undefined -->
<CrudTable :row-key="(row) => row.key" />

<!-- ✅ 正确：传属性名字符串 -->
<CrudTable row-key="key" />
```

---

## 异步与并发规范

### 同步阻塞操作必须放入线程池

FastAPI 是异步框架，**任何 CPU 密集型或同步 I/O 操作都会阻塞事件循环**，导致所有请求卡死。

```python
import asyncio
async def blocking_operation():
    def _sync_blocking():
        # pandas.read_excel(), osmnx.graph_from_place(), openai SDK 等
        return result
    return await asyncio.to_thread(_sync_blocking)
```

**典型场景：** OSMnx 路网下载、pandas 读写 Excel/CSV、openai 同步 SDK 调用、大文件 I/O。

### Tortoise ORM 的线程安全（关键）

**严禁**在线程池回调中调用 Tortoise ORM 的任何方法。Tortoise 必须在事件循环中 `await`。

```python
# ❌ 错误：在线程中调用 ORM
def _bad():
    user = User.get(id=1)   # 会报错或被吞掉

# ✅ 正确：先异步查询，再线程池处理其他事
user = await User.get(id=1)
def _process_data():
    df = pd.DataFrame(user.data)
    return df.to_dict()
result = await asyncio.to_thread(_process_data)
```

### 耗时 API 的超时设置

前端调用可能长时间阻塞的接口（导入、清空、下载大文件）必须设 `{ timeout: 0 }`。默认 axios 超时约 12 秒。

### 耗时任务全局弹窗进度展示

对于 > 30 秒的耗时操作，禁止在页面内嵌进度条（切换页面会销毁）。必须使用**全局任务进度面板**：

```
Pinia Store (taskProgress) → TaskProgressPanel.vue (Layout 级 Teleport，右下角悬浮)
     → 轮询 GET /xxx/progress (后端写入 cache/xxx_progress.json)
```

**两种进度模式：**
- **真实进度**：后端写入状态文件，前端轮询（如 GeoNames 中文名填充）
- **模拟进度**：后端同步返回，前端 `setInterval` 模拟 10→85%（如路网 OSM 下载）

**Store 接口：**

```javascript
import { useTaskProgressStore } from '@/store/modules/taskProgress'
const store = useTaskProgressStore()
const taskId = store.startTask('填充行政区中文名', () => { /* retryHandler */ })
store.updateProgress(taskId, { progress: 30, message: '下载中...', phase: 'allCountries.zip' })
store.finishTask(taskId, '完成')
store.failTask(taskId, { message: '下载失败', detail: 'peer closed...' })
```

**后端进度状态文件格式（`cache/xxx_progress.json`）：**

```python
_progress = {
    "status": "idle",       # idle | downloading | parsing | bridging | done | error
    "phase": "",
    "progress": 0,          # 0-100
    "message": "",
    "detail": "",           # 错误详情（前端 hover 展开）
}
```

**已接入全局面板的模块：**

| 模块 | 页面文件 | 进度类型 |
|------|----------|----------|
| 行政区中文名填充 | `region/index.vue` | 真实进度（轮询后端） |
| 路网下载 (OSM) | `road-network/index.vue` | 模拟进度（同步返回） |
| 边界下载 (GADM) | `region-boundary/index.vue` | 模拟进度（同步返回） |

### 下载断点续传与重试

大文件下载（> 50MB）必须支持断点续传：
1. 临时文件使用 `.tmp` 后缀
2. 失败时**不清除** `.tmp` 文件
3. 重试时发 `Range: bytes={resume_pos}-` 头从断点续传
4. 下载完成后 `os.rename(tmp, final)` 原子操作
5. 后端错误写入进度状态文件（不抛异常），前端通过轮询感知失败

**Python 实现：**

```python
async def _download_httpx(client, url, filepath, label):
    tmp = filepath + ".tmp"
    headers = {}
    if os.path.exists(tmp):
        resume_pos = os.path.getsize(tmp)
        headers["Range"] = f"bytes={resume_pos}-"
    try:
        async with client.stream("GET", url, headers=headers, timeout=600) as resp:
            if resp.status_code not in (200, 206):
                resume_pos = 0
                os.remove(tmp)
                # 重新请求不带 Range 头
            mode = "ab" if resume_pos > 0 else "wb"
            with open(tmp, mode) as f:
                async for chunk in resp.aiter_bytes():
                    f.write(chunk)
        os.rename(tmp, filepath)  # 原子操作
    except Exception as e:
        # .tmp 保留！不清除！
        raise
```

**失败重试流程：**
```
第1次下载：40/400MB → 网络中断 → .tmp 保留 (40MB)
用户点击 [重试] → Range: bytes=41943040-
→ 服务器返回 206 Partial Content → 从 40MB 续传 ("ab" 追加)
→ 完成后 os.rename(.tmp → final)
```

### 大文件多线程分块下载（设计草案）

> 适用于 > 200MB 的超大文件，当前 GeoNames 单流续传已满足需求。

```python
async def download_chunked(url, filepath, chunk_count=4, chunk_size_mb=50):
    # 1. HEAD 获取 Content-Length
    # 2. 并行下载每块 → .part0, .part1 ...
    #    每块用 Range: bytes=start-end
    #    跳过已完成的 .part
    # 3. 按序合并 → 最终文件
    # 4. 清理 .part 文件
```

### 下载器统一读取系统代理配置

所有文件下载功能（GeoNames、GADM、OSMnx）必须从 `system_config` 表统一读取代理配置：

```
系统管理 → 下载配置页面 → 用户填写代理 → 保存到 system_config 表
                                           ↓
每个下载器从 system_config_controller.get_value("download_proxy") 读取
```

| 下载器 | HTTP 库 | 代理注入方式 |
|--------|---------|-------------|
| GeoNames | `httpx.AsyncClient` | `AsyncClient(proxy=proxy_url)` |
| GADM | `httpx.AsyncClient` | 同上，通过 `_get_proxy()` 辅助函数 |
| OSMnx | `requests`（线程池） | 下载前通过 `_set_proxy()` 设置 `HTTPS_PROXY` 环境变量 |

**OSMnx 线程池场景的特殊处理：**

```python
# controller 层：下载前从系统配置读取代理
proxy_url = await system_config_controller.get_value("download_proxy", "")

def _set_proxy():
    if proxy_url:
        os.environ["HTTPS_PROXY"] = proxy_url
        os.environ["HTTP_PROXY"] = proxy_url

# 通过闭包传给线程池
result = await loop.run_in_executor(None, functools.partial(
    OSMnxDownloader.download_by_boundary, ..., _proxy_setup=_set_proxy,
))
```

注意：`requests`（OSMnx）在线程池中无法调用异步 ORM，必须通过闭包在进入线程池前完成配置读取。

---

## 数据库迁移与部署

### 本地迁移

```bash
make migrate   # 或 aerich migrate
make upgrade   # 或 aerich upgrade
make clean-db  # 删除 migrations/ 和 db.sqlite3
```

### Docker 部署中的 SQLite 坑

- 数据库文件**必须放在子目录**（如 `data/db.sqlite3`），Docker volume 挂载不存在的文件时会创建空目录
- volume 使用**目录挂载**：`./data:/opt/app/data`，不要用文件挂载
- 首次部署时容器内 `mkdir -p data` 确保目录存在

### entrypoint.sh 中的迁移超时

`aerich upgrade` 可能因 Tortoise ORM 异步连接未关闭而卡住，用 `timeout` 包装：

```sh
timeout 120 aerich upgrade 2>/dev/null
AERICH_EXIT=$?
if [ $AERICH_EXIT -eq 124 ]; then
    echo "Migration timeout, continuing..."
fi
```

### Docker 构建注意

- `.dockerignore` 只排除 `web/.env.local` 和 `web/.env.*.local`，**不要排除** `.env.production`（含构建变量 `VITE_BASE_API`）
- SVG logo 不加固定 `width`/`height`，只保留 `viewBox`，由 `unplugin-icons` (1em) + CSS 控制

---

## 路网数据中心模块指导（Road Network Data Center）

### 数据模型

所有子模块共用 `Region` 表，通过 `region_type` (COUNTRY/STATE/CITY) + `parent_id` 自引用形成树：

```
COUNTRY (parent_id=null)
  └── STATE (parent_id=国家.id)
       └── CITY (parent_id=行政区.id)
```

**Region 关键字段：**

| 字段 | 类型 | 说明 |
|---|---|---|
| name | VARCHAR(200) | 名称（中文或英文） |
| code | VARCHAR(20) | ISO 代码（国家用 alpha-2） |
| iso_alpha2/3 | VARCHAR(2/3) | ISO 3166-1 |
| region_type | ENUM | COUNTRY / STATE / CITY |
| parent_id | FK→region.id | 父级引用 |
| capital | VARCHAR(200) | 首都/首府 |
| population | BIGINT | 人口 |
| area | FLOAT | 面积 (km²) |
| latitude / longitude | FLOAT | 经纬度 |

**国家 ISO 数据导入**：使用 `pycountry` 库批量导入三级数据（~249 国家 + ~3590 一级行政区 + ~1456 二级行政区）。

**边界文件**（`RegionBoundary`）：关联 region，记录 file_name/file_type/file_path/download_status，通过 GADM API 下载 GeoJSON。

**路网文件**（`RoadNetwork`）：关联 region，记录 file_name/file_type/file_path/node_count/edge_count/download_status，通过 OSMnx 下载。两种模式：
- **边界模式** (`boundary`)：读取 RegionBoundary GeoJSON → 提取 polygon → `ox.graph_from_polygon()`
- **地名模式** (`name`)：构造 "区域名, 国家名" → `ox.graph_from_place()`

### 前端布局

页面使用**左侧树 + 右侧详情**的双面板布局（见前端双面板布局规范）。NTree 必须加 `virtual-scroll`。

**树数据结构（后端返回）：**

```json
[
  {"id": 1, "label": "中国", "code": "CN", "region_type": "COUNTRY",
   "children": [
     {"id": 2, "label": "北京", "code": "CN-BJ", "region_type": "STATE",
      "children": [{"id": 3, "label": "东城区", "code": "CN-BJ-DC"}]}
   ]}
]
```

**树节点选中事件处理（⚠️ option 是数组）：**

```javascript
function onNodeSelect(keys, option) {
  if (keys.length === 0) {
    selectedNode.value = null
    return
  }
  const node = Array.isArray(option) ? option[0] : option
  selectedNode.value = node
  loadNodeDetail(node.id)   // GET /region/get?region_id=...
  loadChildren(node.id)     // GET /region/children?parent_id=...
}
```

### 耗时操作注意

- 涉及大量数据处理的请求（导入、清空、OSM 下载），前端必须设 `{ timeout: 0 }`
- 后端异步操作放入 `asyncio.to_thread()`（如 OSMnx 下载）
- 使用全局任务进度面板展示进度

### 关键踩坑

- `getRegionById` 和 `getRegionChildren` 直接传值（非对象），内部通过 `{ params: { key: value } }` 传递
- `NTree` 的 `@update:selected-keys` 第二个参数 `option` 是数组，取 `option[0]` 拿到实际节点
- `import.meta.env` 不能直接写在 Vue template 表达式中，需在 `<script setup>` 中用 `computed` 定义
- NTree 搜索框放在 NCard 默认插槽（树的上方），绑定 `:pattern` + `:filter` 实现大小写不敏感过滤

### 控制器非 CRUDBase 模式

对于复杂模块（如统计中心的 ReportService），可以不继承 CRUDBase，直接创建独立 Service 类，手动管理 Tortoise ORM 操作。路由中通过权限检查确保安全性。

### 软删除模式

```python
is_deleted = fields.BooleanField(default=False)
# 查询时过滤
q = Q(is_deleted=False)
# 删除时标记而非真删
obj.is_deleted = True
await obj.save()
```

---

## 完整开发流程速查（新模块）

### 后端

1. **创建模型** → `app/models/admin.py` 添加类（继承 `BaseModel, TimestampMixin`）
2. **创建 Schema** → `app/schemas/xxx.py` 定义 `Create`/`Update` 类
3. **创建 Controller** → `app/controllers/xxx.py`（继承 CRUDBase）
4. **导出 Controller** → `app/controllers/__init__.py`
5. **创建 API 路由** → `app/api/v1/xxx/__init__.py`（创建 `xxx_router`）+ `api/v1/xxx/xxx.py`
6. **注册路由** → `app/api/v1/__init__.py` 导入并注册（加 `DependPermission`）
7. **数据库迁移** → `make migrate && make upgrade`
8. **添加种子数据**（可选）→ `app/core/init_app.py`

### 前端

9. **前端注册 API** → `web/src/api/index.js`
10. **创建前端页面** → `web/src/views/xxx/index.vue`（必须用 `CrudTable` + `useCRUD`）
11. **菜单配置** → 后台「菜单管理」添加菜单（路径 `/xxx`，组件 `/xxx`）+ 角色分配权限

---

## 常见错误速查表

| 错误现象 | 原因 | 解决方案 |
|---|---|---|
| 树节点选中报 422 | option 是数组，解构 `.id` 拿到 undefined | 取 `option[0].id` |
| 页面右侧内容溢出 | 使用了 `NSpace` 或未设 `overflow: hidden` | 用 flex + `overflow: hidden` 布局 |
| 上传文件报 `UnicodeDecodeError` | 审计日志中间件解析了 multipart 请求体 | 上传路径加入 `exclude_paths` |
| 前端请求长时间等待后超时 | 未设 `timeout: 0` | 添加 `{ timeout: 0 }` |
| 异步接口卡死所有请求 | 同步阻塞未放入线程池 | 用 `asyncio.to_thread()` |
| Tortoise ORM 在线程中报错 | 线程中调用了 ORM | 先 `await` 查询，再线程池处理 |
| `CrudModal` 保存无反应 | 缺少 `<NForm ref="modalFormRef">` | 添加 ref 绑定 |
| `NModal` 按钮不显示 | `preset="card"` 未用 footer 插槽 | 使用 `#footer` 插槽 |
| 文件下载返回 HTML 而非文件 | Blob 被拦截器错误处理 | 拦截器先判断 `data instanceof Blob` |
| `import.meta.env` 在模板中报错 | Vue 模板不支持 | 在 `<script>` 中用 `computed` 定义 |
| SVG logo 导致布局变形 | 固定 `width="2048" height="2048"` | 只保留 `viewBox`，由 CSS 控制尺寸 |
| Docker 构建后 `VITE_BASE_API` 为空 | `.dockerignore` 排除了 `.env.production` | 只排除 `web/.env.local` |
| SQLite 无法打开数据库 | Docker volume 挂载不存在的文件创建了空目录 | volume 用目录挂载 `./data:/opt/app/data` |
| `aerich upgrade` 卡住不退出 | Tortoise ORM 异步连接未关闭 | 用 `timeout 120` 包装 |
| NDataTable virtual-scroll + flex-height 行不渲染 | 两者冲突 | 去掉 `flex-height`，用 `:max-height` 绑定固定值 |
| NDataTable row-props onClick 在虚拟滚动下不生效 | 动态 DOM 销毁/重建导致绑定不稳定 | 改用 `v-for` + 自定义 `<div>` 列表 |
| 大文件下载中断需从头开始 | 临时文件在异常时被删除 | 保留 `.tmp`，重试用 `Range` 续传 |
| 耗时任务切换页面后进度条消失 | 进度条嵌入页面内 | 使用全局 TaskProgressPanel + Pinia Store |
| `pip` 依赖冲突 | `requirements.txt` 版本过时 | 与 `pyproject.toml` 保持同步 |
| CSS `calc(100vh - 430)` 报错 | Vue 模板将 calc 当作 JS 表达式 | 加引号：`:max-height="'calc(100vh - 430)'"` |
| CodeMirror 高度为 0 | `.CodeMirror` 不自动填充父容器 | `cmInstance.getWrapperElement().style.height='100%'` + CSS `.CodeMirror{height:100%!important}` |
| 菜单树不显示 | 后端返回的 children 字段名不是 `children` | 确保树数据字段名为 `children` |
| 登录页/界面布局变形 | SVG logo 带固定像素尺寸 | 移除 `width`/`height`，只保留 `viewBox` |
| 下载失败后前端无法感知错误 | 后端异常被吞掉 | 后端失败写进度状态文件 `_update_progress("error",...)` |
| 大文件下载速度慢（单线程） | 单流下载受单连接带宽限制 | 多线程分块下载 `Range: bytes=start-end` |
| Leaflet 瓦片 Canvas 截取返回 0 | Leaflet 用 CSS `transform: translate3d()` 定位瓦片，`style.left/top` 为空 | 用 `getBoundingClientRect()` 获取实际位置 |
| Leaflet `tile.el` 不是 `<img>` | Leaflet 用 `<div class="leaflet-tile"><img/></div>` 包裹 | 用 `el.querySelector('img')` 递归取 `<img>` |
| Canvas 绘制跨域瓦片报 SecurityError | 底图瓦片来自外部 CDN，无 CORS 头 | 用 `html-to-image` 库截取完整 DOM（或仅导出同源路网瓦片） |
| **UnoCSS `text-*` 字体极小（如 `text-base` 只显示 4px）** | `web/src/styles/global.scss` 设 `html { font-size: 4px }`，导致 1rem=4px，UnoCSS 的 rem 字体类全部缩到 1/4 | 在该页面加 `<style scoped>` 用 `!important` + px 覆盖：`.text-base { font-size: 16px !important; line-height: 24px !important; }` 等。禁止直接改全局 `html` 基准 |
| **Tab 内容区无法滚动（内容溢出但无滚动条）** | flex 布局链在中途断裂：`.n-tab-pane` 默认 `display:block`（子元素 `flex-1` 垂直失效）；中间容器缺少 `overflow:hidden` + `min-height:0`；Naive UI 组件（NSpin/NTabs）的 wrapper 未设置 flex 约束 | **3 层修复**：① index.vue 深度覆盖 `.n-tab-pane { display:flex; flex-direction:column }`、`.n-spin-container { flex:1; min-height:0; overflow:hidden }`；② 每个 Tab 组件的根 div 和所有 flex 列容器加 `overflow:hidden`；③ 双栏布局的左右栏容器加 `min-height:0; overflow:hidden`。验证方法：Playwright 注入数据后检查 `el.clientHeight` 是否稳定（ΔCH=0）

---

## 强制规则汇总（29 条）

1. **后端**：所有控制器继承 `CRUDBase`，所有路由加 `summary` 中文描述
2. **前端**：所有列表页必须用 `CrudTable`，禁止手写 `NDataTable` + 分页
3. **双面板**：必须用 flex + `overflow: hidden`，禁止用 `NSpace`
4. **树组件**：必须加 `virtual-scroll`，`@update:selected-keys` 回调取 `option[0]`
5. **异步**：同步阻塞操作必须 `asyncio.to_thread()`，Tortoise ORM 禁止在线程池调用
6. **超时**：耗时后端接口前端设 `timeout: 0`，并加入审计中间件排除列表
7. **权限**：前端按钮用 `v-permission`，值为 `method+path`
8. **响应**：统一使用 `Success` / `SuccessExtra` / `Fail`
9. **文件下载**：axios 拦截器必须处理 Blob 类型
10. **数据库**：模型必须带 `description` 和 `index`（查询字段）
11. **Docker**：SQLite 卷用目录挂载（`./data:/opt/app/data`），不用文件挂载
12. **Docker**：`.dockerignore` 只排除 `web/.env.local`，不排除 `.env.production`
13. **入口**：`entrypoint.sh` 用 `timeout` 包装 `aerich upgrade`，防止异步连接卡死
14. **SVG**：logo 不加固定 `width`/`height`，只留 `viewBox`，由 CSS 控制
15. **依赖**：新增依赖后检查 `typing-extensions` 等共享依赖的版本兼容性
16. **级联列表**：逐层深入选择用 `v-for` + 面包屑，禁止 NDataTable + virtual-scroll + row-props
17. **keepAlive**：子路由不会自动缓存，`onMounted` 即足够；不依赖 `onActivated`
18. **耗时任务弹窗**：> 30 秒的耗时操作使用全局 TaskProgressPanel，不嵌入页面
19. **断点续传**：大文件下载（> 50MB）失败保留 `.tmp` 文件，重试用 `Range` 头续传
20. **分块下载**：超大文件（> 200MB）用多线程分块，并行下载后合并
21. **下载失败通知**：后端失败写进度状态文件，前端轮询感知并显示重试
22. **Leaflet 本地化**：所有 Leaflet 资源（CSS/JS/marker 图标）下载到 `web/public/lib/leaflet/`，index.html 引用本地路径
23. **Leaflet 瓦片截取**：用 `getBoundingClientRect()` 获取瓦片位置（非 `style.left/top`），用 `el.querySelector('img')` 取 img 元素
24. **图层导出**：包含跨域瓦片或 DOM 控件时用 `html-to-image` 库，纯同源路网可用 Canvas
25. **PNG 元数据**：导出图片的描述（description）写入 JSON 元数据（中心点、作者、路网统计），后端用 Pillow `PngInfo` 写入 tEXt 块
26. **UnoCSS 字体**：全局 `html { font-size: 4px }` 使 1rem=4px，UnoCSS 的 `text-*` 类（rem）全部缩到 1/4。新建页面时**必须在 `<style scoped>` 中用 `!important` + px 覆盖 `text-xs` 到 `text-xl` 的 `font-size` 和 `line-height`**，禁止直接改全局 `html` 基准
27. **CrudTable rowKey**：`row-key` prop 只接受 String（属性名），**不能传函数**。`(row) => row.key` 会被转为字符串导致所有行 key 为 undefined，checkbox 无法选中
28. **热更新不自动触发**：改完代码后**禁止**主动询问"是否需要热更新？"或自动执行部署脚本。只有用户明确说出"热更新"、"部署到服务器"、"更新到远程"时才执行 `hot-update.sh`（前端）或 `hot-update-be.sh`（后端）
29. **Tab 内容区滚动布局链**（NTabs + NTabPane 场景）：整条 flex 列布局链每层必须同时具备 `display:flex; flex-direction:column` + `min-height:0` + `overflow:hidden`。`.n-tab-pane` 默认 `display:block` 必须用 `:deep()` 覆盖为 `flex`；`.n-spin-container` 必须补 `flex:1; min-height:0; overflow:hidden`；双栏容器和左右栏加 `min-height:0; overflow:hidden`。验证方法：Playwright 注入数据后检查 `el.clientHeight` 是否稳定（ΔCH=0）

---

## 后端功能模块速查

### 数据模型总览（`app/models/admin.py`）

| 模型 | 继承 | 关键字段 |
|---|---|---|
| User | BaseModel, TimestampMixin | username, email, password_hash, is_superuser, is_active, roles(M2M→Role) |
| Role | BaseModel, TimestampMixin | name, desc, menus(M2M→Menu), apis(M2M→Api) |
| Api | BaseModel, TimestampMixin | path, method, summary, tags |
| Menu | BaseModel, TimestampMixin | title, name, path, component, icon, parent_id, menu_type, order |
| Dept | BaseModel, TimestampMixin | name, parent_id, leader, phone |
| DeptClosure | BaseModel, TimestampMixin | ancestor_id, descendant_id, depth |
| AuditLog | BaseModel, TimestampMixin | user_id, username, method, path, summary, ip, status_code |
| PixelAccount | BaseModel, TimestampMixin | name, tenant_address, token, users(M2M→User) |
| Defect | BaseModel, TimestampMixin | pixel_account_id, car_id, defect_type, latitude, longitude, image_url |
| Track | BaseModel, TimestampMixin | pixel_account_id, car_id, start_time, end_time, distance_km, points(JSON) |
| Region | BaseModel, TimestampMixin | name, code, iso_alpha2/3, region_type(ENUM), parent_id(self-FK), capital, population, area, lat/lon |
| RegionBoundary | BaseModel, TimestampMixin | region(FK), file_name, file_type, file_path, download_status |
| RoadNetwork | BaseModel, TimestampMixin | region(FK), file_name, file_type, file_path, node_count, edge_count, download_status, bbox, stats(JSON) |
| Skill | BaseModel, TimestampMixin | title, content, users(M2M→User) |
| AIProxy | BaseModel, TimestampMixin | name, url, token, model, users(M2M→User) |
| Workspace | BaseModel, TimestampMixin | name, desc, users(M2M→User) |
| OriginalSheet | BaseModel, TimestampMixin | workspace(FK), file_name, file_path, sheet_names(JSON) |
| AnalysisSheet | BaseModel, TimestampMixin | workspace(FK), original_sheet(FK), name, prompt, content(JSON), data_hash |
| Document | BaseModel, TimestampMixin | workspace(FK), name, file_path, file_type, source_type, source(JSON) |
| Report | BaseModel, TimestampMixin | workspace(FK), title, content(HTML), filter_template(JSON) |
| SystemConfig | BaseModel, TimestampMixin | key, value |

### 控制器方法速查

#### 基础模块（CRUDBase 继承）

| 模块 | 路由 | 控制器 | 自定义方法（除 CRUD 五件套） |
|---|---|---|---|
| 用户管理 | `/user` | UserController | `get_by_email`, `get_by_username`, `create_user`, `update_last_login`, `authenticate`, `update_roles` |
| 角色管理 | `/role` | RoleController | `is_exist`, `update_roles(menu_ids, api_infos)` |
| 菜单管理 | `/menu` | MenuController | `get_by_menu_path`, `scan_views`（扫描前端视图文件夹） |
| API 管理 | `/apis` | ApiController | `refresh_api`（扫描所有路由自动注册） |
| 部门管理 | `/dept` | DeptController | `get_dept_tree`, `get_dept_info`, `update_dept_closure`, `create_dept`, `update_dept`, `delete_dept` |
| 像素账户 | `/pixel-account` | PixelAccountController | `update_users`, `create_account`, `update_account`（含 Token 自动刷新） |
| AI 代理 | `/ai-proxy` | AIProxyController | `get_by_name`, `create_or_update`, `get_accessible`, `check_permission`, `update_users` |
| Skill 管理 | `/skill` | SkillController | `get_accessible_skills`, `check_permission`, `update_users` |

#### 数据工作台模块

| 路由 | 控制器 | 关键方法 |
|---|---|---|
| `/workspace` | WorkspaceController (CRUDBase) | `update_users`, `upload_sheet`, `list_sheets`, `delete_sheet`, `export_sheet`, `analyze`（AI 分析表格）, `correlate`（AI 关联分析）, `list_analyses`, `delete_analysis`, `batch_delete_analyses`, `clear_analyses`, `export_analysis`, `batch_export_analyses`, `copy_to_workspace` |
| `/workspace/static-file` | StaticFileController (CRUDBase) | `upload`, `list_files`（按层级）, `get_file`, `update_file`, `delete_file`, `batch_delete`, `get_by_short_token`, `cv_process`（OpenCV 处理）, `ai_process`（AI 图片优化）, `ocr_extract`, `import_from_road_material`, `list_material_regions`, `list_materials_by_region`, `list_image_files` |
| `/document` | DocumentController | `list_by_workspace`, `get`, `upload`, `create_from_text`, `delete`, `batch_delete`, `get_content`, `update_content`, `clear_by_workspace`, `ai_analyze` |
| `/report` | ReportController (CRUDBase) | `export_pdf`, `export_word`, `export_html` |

#### 路网数据中心模块

| 路由 | 控制器 | 关键方法 |
|---|---|---|
| `/region` | RegionController | `list_regions`（多条件搜索）, `create_region`, `update_region`, `get_tree`, `get_children`, `import_countries`（pycountry 批量导入三级数据）, `clear_all`, `export_data`, `batch_update`, `fill_geonames`（GeoNames 中文名填充，带进度）, `download_boundary`（GADM API）, `upload_boundary`, `delete_boundary`, `clear_boundaries`, `export_boundary`, `download_road_network`（OSMnx，边界/地名两种模式）, `upload_road_network`, `delete_road_network`, `clear_road_networks`, `export_road_network`, `analyze_road_network`, `filter_road_network`, `segment_road_network`, `get_tile`（瓦片服务）, `warm_tile_cache`, `get_cached_fields` |
| `/road-material` | RoadMaterialController (→ StaticFileController 代理) | `upload`, `list`, `update`, `delete`, `get_by_short_token`, `cv_process`, `ai_process` |

#### 轨迹 & 病害模块

| 路由 | 控制器 | 关键方法 |
|---|---|---|
| `/defect` | DefectController | `get_user_accounts`, `sync`（同步病害数据）, `clear`, `list_defects` |
| `/track` | TrackController | `get_user_accounts`, `get_car_types`, `get_cars`, `sync`（同步轨迹数据）, `clear`, `list_tracks` |
| `/vehicle` | VehicleController | `get_user_accounts`, `get_car_types`, `get_cars`, `check_status`, `get_info`, `full_check`（一站式检测）, `refresh_status`, `query_flow`（数据流量） |

#### 系统 & 国际化模块

| 路由 | 控制器 | 关键方法 |
|---|---|---|
| `/sysconfig` | SystemConfigController | `init_defaults`, `get_all`, `get_value`, `set_value`, `set_all`, `test_proxy` |
| `/i18n` | I18nController | `get_all`, `get_list`, `update`, `batch_update`, `export_data`, `import_data`, `ai_generate`（AI 翻译）, `scan_frontend`（扫描硬编码）, `replace_hardcoded` |

### 后端工具类速查（`app/utils/`）

| 工具 | 文件 | 核心功能 |
|---|---|---|
| 密码加密 | `password.py` | `get_password_hash`, `verify_password` (argon2 via passlib) |
| JWT | `jwt_utils.py` | `create_access_token` (PyJWT) |
| 文档转换 | `doc_to_md.py` | `file_to_markdown` → PDF/DOCX/PPTX/XLSX/CSV → Markdown |
| 图片处理 | `image_processor.py` | `ImageProcessor`: resize, rotate, crop, flip, add_border, brightness, contrast, color_space, blur, morphology, smooth, histogram_eq, remove_bg (grabcut/threshold) |
| 路网分析 | `road_network_analyzer.py` | `RoadNetworkAnalyzer`: get_info, to_geojson, get_highway_types, filter_by_highway, segment（GraphML→GPKG 双向转换） |
| 路网瓦片 | `road_network_tiler.py` | 路网 GPKG → XYZ 瓦片 PNG（多缩放级别，缓存热数据） |
| OSMnx 下载 | `osmnx_downloader.py` | `OSMnxDownloader`: download_by_boundary (GeoJSON polygon), download_by_name |
| GADM 下载 | `gadm_downloader.py` | `GADMDownloader`: download (ISO alpha-3 + level), check_available |
| GeoNames 下载 | `geonames_downloader.py` | `GeoNamesChineseDownloader`: download_and_parse, build_mapping, apply_mapping（断点续传 + 进度状态文件） |
| 像素 API | `pixel_api.py` | `get_base_info`, `get_user_auth_info`, `reverse_geocode_osm`, `reverse_geocode_mapbox` |
| 火山引擎视觉 | `volcengine_visual.py` | 火山引擎视觉 API 封装（AI 图片处理） |
| HTTP 工具 | `http_utils.py` | `make_download_response`（统一文件下载响应） |
| 外部 API | `xiangsu_api.py` | 像素平台外部 API 封装 |

### 已实现页面速查

| 页面 | 路由 | 前端组件 | 特点 |
|---|---|---|---|
| Skill 管理 | `/skill` | `views/skill/index.vue` | vditor 所见即所得编辑器 + CrudTable + useCRUD |
| AI 代理管理 | `/ai-proxy` | `views/ai-proxy/index.vue` | 标准 CrudTable + useCRUD |
| 数据工作台 | `/workspace` | `views/statistic-center/data-workbench/index.vue` | 左侧工作区 + 右侧 NTabs 多数据源，卡片式布局 |
| 统计中心（报告） | `/report` | `views/statistic-center/report/index.vue` | CodeMirror 编辑 → PDF/Word/HTML 导出 |
| 路网数据中心 | `/region` | `views/network/road-network/index.vue` | NTree 双面板 + OSMnx 下载 |
| 路网工作台 | `/region/road-network` | `views/network/road-network-workbench/index.vue` | Leaflet 多底图 + 瓦片叠加 + 图层导出 + AI/CV 处理 |
| 路网素材 | `/region/road-material` | `views/network/road-material/index.vue` | 上传/编辑/删除 + AI/CV 处理 + 预览（缩放旋转+GPS地图） |
| 国际化 | `/i18n` | `views/system/i18n/index.vue` | 翻译编辑 + AI 批量翻译 + 导入导出 |

### 路网工作台前端库

| 库 | 路径 | 用途 |
|---|---|---|
| Leaflet 1.9.4 | `web/public/lib/leaflet/` | 地图渲染 (CSS/JS/marker 图标) |
| html-to-image 1.11.11 | `web/public/lib/html-to-image/` | DOM → Canvas/PNG 截取（图层导出） |

Leaflet 控件：缩放 (zoom)、底图切换、路网瓦片叠加、图例、坐标显示、**方位罗盘** (CompassControl, 右上角)、**比例尺** (L.control.scale, 左下角)、**图层导出按钮** (ExportControl, 缩放下方)。



---

## 脚手架工具（Scaffolding CLI）

项目内置模块脚手架 CLI 工具 `scripts/scaffold.py`，一键生成新模块的全部样板代码，遵循所有强制规则。

### 用法

```bash
# 基本用法：指定模块名 + 中文名
python scripts/scaffold.py --name category --cn 分类 --fields "name:str:50:分类名:true,sort:int::排序"

# 交互式模式（逐步引导输入）
python scripts/scaffold.py -i

# JSON 配置文件模式（可复用）
python scripts/scaffold.py --config scaffold_defs/gallery.json

# 预览模式（不写文件，仅预览）
python scripts/scaffold.py --name tag --cn 标签 --dry-run
```

### 参数说明

| 参数 | 说明 | 示例 |
|------|------|------|
| `--name` | 模块名（snake_case），用于文件名和 Python 类名 | `announcement` |
| `--cn` | 中文名，用于路由 summary 和前端页面标题 | `公告` |
| `--route` | 路由前缀，默认从 name 自动推导（kebab-case） | `/announcement` |
| `--fields` | 字段列表，逗号分隔。格式：`name:type:max_length:desc:index` | 见下方 |
| `--group` | 前端 views 子目录，默认 `system` | `network`, `pixel` |
| `--icon` | 菜单图标（Material Symbols 格式） | `material-symbols:category` |
| `--config` | JSON 配置文件路径（相对项目根目录） | `scaffold_defs/xxx.json` |

### 字段格式

每个字段由 `:` 分隔的 5 个值组成：

```
字段名:类型:长度:中文描述:是否索引
```

- **类型**：`str` → CharField, `int` → IntField, `float` → FloatField, `bool` → BooleanField, `text` → TextField, `json` → JSONField, `datetime` → DatetimeField
- **长度**：仅 `str` 类型需要，作为 `max_length`。留空则用 `null=True` 替代
- **中文描述**：写入 `description=` 和前端列标题
- **索引**：`true`/`1`/`yes` → `index=True`

**示例：**

```bash
--fields "name:str:50:名称:true,content:text::文章内容,is_published:bool::发布状态:true"
```

### 生成的文件

脚手架自动创建/修改以下 9 个位置：

| # | 操作 | 文件 | 内容 |
|---|------|------|------|
| 1 | 创建 | `app/schemas/{name}.py` | `XxxCreate` + `XxxUpdate` Pydantic Schema |
| 2 | 创建 | `app/controllers/{name}.py` | `XxxController(CRUDBase)` + 单例 |
| 3 | 创建 | `app/api/v1/{name}/__init__.py` | 模块路由聚合 |
| 4 | 创建 | `app/api/v1/{name}/{name}.py` | 5 个 API 端点（list/get/create/update/delete） |
| 5 | 修改 | `app/models/admin.py` | 追加 `Xxx(BaseModel, TimestampMixin)` 模型类 |
| 6 | 修改 | `app/api/v1/__init__.py` | 注册路由 + `DependPermission` |
| 7 | 修改 | `app/controllers/__init__.py` | 导出 controller 单例 |
| 8 | 修改 | `web/src/api/index.js` | 5 个前端 API 函数 |
| 9 | 创建 | `web/src/views/{group}/{name}/index.vue` | CrudTable + useCRUD 完整页面 |

### 生成后的手动步骤

脚手架生成代码后，仍需执行以下操作：

```bash
# 1. 数据库迁移
make migrate && make upgrade

# 2. 前端构建
cd web && pnpm install && pnpm build
```

然后在**后台「菜单管理」**中添加菜单：
- 路径：`/{route}`（如 `/tag`）
- 组件：`/{group}/{name}`（如 `/system/tag`）

最后在**角色管理**中给角色分配新菜单和 API 权限。

### JSON 配置文件格式

```json
{
  "name": "gallery",
  "cn_name": "图库",
  "route": "/gallery",
  "group": "network",
  "icon": "material-symbols:photo-library",
  "fields": [
    "title:str:200:标题:true",
    "url:str:500:图片地址",
    "width:int::宽度(px)",
    "sort_order:int::排序:true"
  ]
}
```

### 内置规则保障

脚手架自动遵循以下强制规则（无需人工检查）：

1. ✅ 模型继承 `BaseModel, TimestampMixin`，字符串字段有 `max_length` + `description` + `index`
2. ✅ Controller 继承 `CRUDBase[Model, Create, Update]`，单例小写命名
3. ✅ 路由每个端点有 `summary` 中文描述，分页参数有 `ge=1` 校验
4. ✅ 路由注册加 `DependPermission` 依赖
5. ✅ 响应使用 `Success` / `SuccessExtra` / `Fail`
6. ✅ 前端使用 `CrudTable` + `useCRUD` + `CrudModal` + `#footer` 插槽
7. ✅ 表单使用 `<NForm ref="modalFormRef">`
8. ✅ 双面板字符字段自动生成 QueryBar 搜索项

---

## Cache Stability（保留原 AGENTS.md 结构）

- **Frequently-rebuilt files**: Generated code, lockfiles, build artifacts
- **Stable scaffolding**: Config files, project instructions, model cards
- **Append, don't reorder**: New context goes at the end of the request; reordering invalidates cache

## Guidelines

- Follow existing code style and patterns
- Write tests for new functionality
- Keep changes focused and atomic
- Document public APIs
- Update this file when project conventions change

---

## 开发运维

### 项目管理脚本 `dev.sh`

所有运维操作统一入口：`./dev.sh {命令}`

| 命令 | 说明 |
|---|---|
| `./dev.sh start` | 启动前后端（后台运行，日志写入 `logs/`） |
| `./dev.sh stop` | 停止前后端（含 `fuser -k` 端口强制释放） |
| `./dev.sh restart` | 重启 = stop → start |
| `./dev.sh status` | 查看运行状态、PID、端口 |
| `./dev.sh logs` | 最近日志（两端各 20 行） |
| `./dev.sh logs be` | 仅后端日志（50 行） |
| `./dev.sh logs fe` | 仅前端日志（50 行） |
| `./dev.sh logs tail` | 实时追踪日志（Ctrl+C 退出） |
| `./dev.sh log-clear` | 清空日志文件 |
| `./dev.sh build` | 仅构建前端产物 |

**端口**：
- 前端：`http://localhost:3100`
- 后端：`http://localhost:9999`
- API 文档：`http://localhost:9999/docs`

**停止机制**：`stop` 先通过 PID 文件杀进程，再用 `fuser -k` 按端口释放，最后用 `pkill` 兜底清理。确保无论进程如何启动都能完全停止。

### 关键目录

| 目录 | 说明 |
|---|---|
| `app/` | 后端 FastAPI 应用主体 |
| `app/api/v1/` | API 路由层 |
| `app/controllers/` | 业务逻辑控制器 |
| `app/models/` | Tortoise ORM 模型 |
| `app/schemas/` | Pydantic 请求/响应 Schema |
| `app/core/` | 核心模块（权限、JWT、中间件） |
| `web/src/` | 前端 Vue 源码 |
| `web/src/views/` | 视图页面 |
| `web/src/layout/` | 布局组件（侧边栏、顶栏、标签页） |
| `web/src/layout/components/sidebar/` | 全局侧边栏（SideBar → SideLogo + SideMenu） |
| `web/src/components/common/` | 公共组件（DocWorkbenchSidebar 等） |
| `web/src/store/` | Pinia store |
| `web/src/router/` | Vue Router 配置 |
| `web/src/styles/` | 全局样式 |
| `web/src/composables/` | 组合式函数（useCRUD 等） |
| `scripts/` | 后端脚本 |
| `logs/` | 运行日志（由 dev.sh 管理） |

### 前端开发快捷键

**路由**：
- `/workbench` → 功能卡片式工作台（首页）
- `/statistic-center/data-workbench` → 数据工作台
- `/statistic-center/doc-workbench` → 文书工作台
- `/statistic-center/report` → 报告列表
- `/system/*` → 系统管理（用户/角色/菜单等）

**工作台侧边栏**：数据工作台的侧边栏已对齐文书工作台的 `DocWorkbenchSidebar` 设计模式——卡片式列表、搜索过滤、彩色首字母头像、日期+用户数元信息、选中态高亮。

### 常见故障排查

| 问题 | 方案 |
|---|---|
| 端口被占用 | `./dev.sh restart`（自动释放端口） |
| 后端启动失败 | 先 `./dev.sh logs be` 查看错误，常见：缺少依赖 → `.venv/bin/pip install -r requirements.txt` |
| 前端启动失败 | `./dev.sh logs fe`，常见：node_modules 损坏 → `cd web && pnpm install` |
| 依赖模块缺失 | 后端用 `.venv/bin/python`（不是系统 python）；确认 venv 已激活 |

---

*此文件由 `.codewhale/skills/develop_guide.md`（VansRSA 开发核心规则）、`.codewhale/skills/vfa-dev-guide/SKILL.md`（VFA 开发指导）、`.codewhale/skills/road-network-center/SKILL.md`（路网数据中心指导）整合而成。后续新增规范请更新此文件，并保持对其他 skill 文档的引用关系。*

---

## 热更新（部署到服务器）

> 改完代码后，通过脚本一键构建、打包、上传到远程服务器，无需重建 Docker 镜像。

### 服务器信息

| 项目 | 值 |
|---|---|
| 地址 | `http://192.168.0.153:1110` |
| 用户 | `Vance` |
| 密码 | `w570264649+` |
| 鉴权方式 | `token` header（JWT） |

### 触发规则（强制）

> **热更新不能自动触发。** 只有当用户在当前对话中**明确要求**"热更新"、"部署到服务器"、"更新到远程"等时，才执行热更新操作。代码修改完成后**禁止**主动询问"是否需要热更新？"或自动执行部署脚本。

### 前端热更新

修改 `web/` 下的前端代码后，构建 + 打包 + 上传。

**上传接口：** `POST /api/v1/deploy/update-frontend`

**一键命令：**

```bash
cd /home/vance/deepseek_tui/vue-fastapi-admin && bash hot-update.sh -p 'w570264649+'
```

**脚本参数：**
| 参数 | 说明 |
|---|---|
| `--no-build` | 跳过构建，上传已有 `web/dist/` |
| `--build-only` | 仅构建 + 打包，不上传 |
| `-p PASSWORD` | 指定密码（默认从环境变量读取） |

**等同于：**
```bash
# 手动步骤
cd web && pnpm install --silent && pnpm build && cd ..
bash package-frontend.sh --no-build -o hotfix.zip
TOKEN=$(curl -s --noproxy '*' --connect-timeout 10 -X POST http://192.168.0.153:1110/api/v1/base/access_token -H "Content-Type: application/json" -d '{"username":"Vance","password":"w570264649+"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['data']['access_token'])")
curl -s --noproxy '*' -X POST http://192.168.0.153:1110/api/v1/deploy/update-frontend -H "token: $TOKEN" -F "file=@dist_package/hotfix.zip"
```

### 后端热更新

修改 `app/` 下的后端代码后，打包 + 上传。上传后容器自动重启（约 5-15 秒恢复）。

**上传接口：** `POST /api/v1/deploy/update-backend`

**一键命令：**

```bash
cd /home/vance/deepseek_tui/vue-fastapi-admin && bash hot-update-be.sh -p 'w570264649+'
```

**脚本参数：**
| 参数 | 说明 |
|---|---|
| `--build-only` | 仅打包，不上传 |
| `-p PASSWORD` | 指定密码（默认从环境变量读取） |

### 注意事项

- **必须 `--noproxy '*'`**：本地环境有 HTTP 代理（127.0.0.1:7890），连接内网服务器必须绕过（脚本已内置）
- **Token 有效期较短**，若上传报 401，脚本会自动重新获取
- **header 用 `token`**（非 `Authorization: Bearer`），与后端 `AuthControl.is_authed` 对齐
- 前端更新后 **Ctrl+F5** 强制刷新浏览器，Nginx 对 `index.html` 不设强缓存
- 后端热更新上传后容器自动重启，旧代码备份在 `/opt/VansRSA/app_backup/`