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

---

## 强制规则汇总（26 条）

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

---

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

### 路网工作台前端库

| 库 | 路径 | 用途 |
|---|---|---|
| Leaflet 1.9.4 | `web/public/lib/leaflet/` | 地图渲染 (CSS/JS/marker 图标) |
| html-to-image 1.11.11 | `web/public/lib/html-to-image/` | DOM → Canvas/PNG 截取（图层导出） |

Leaflet 控件：缩放 (zoom)、底图切换、路网瓦片叠加、图例、坐标显示、**方位罗盘** (CompassControl, 右上角)、**比例尺** (L.control.scale, 左下角)、**图层导出按钮** (ExportControl, 缩放下方)。

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

*此文件由 `.codewhale/skills/develop_guide.md`（VansRSA 开发核心规则）、`.codewhale/skills/vfa-dev-guide/SKILL.md`（VFA 开发指导）、`.codewhale/skills/road-network-center/SKILL.md`（路网数据中心指导）整合而成。后续新增规范请更新此文件，并保持对其他 skill 文档的引用关系。*