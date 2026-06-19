# VansRSA 开发核心规则
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

### 2.8 级联列表模式（替代 NTree 的多层级选择）

当需要**逐层深入选择**（如 国家 → 行政区 → 城市）而非一次性展开整棵树时，使用**面包屑 + 单区域列表**模式，**禁止**使用 NDataTable + virtual-scroll + row-props 组合。

**为什么不用 NDataTable？**
- `virtual-scroll` 与 `flex-height` 冲突导致行不渲染
- `row-props` 的 `onClick` 在虚拟滚动下不可靠
- 调试成本远高于收益

**正确做法：**

```html
<!-- 面包屑导航 -->
<NBreadcrumb>
  <NBreadcrumbItem>
    <span @click="backToLevel(0)">根</span>
  </NBreadcrumbItem>
  <NBreadcrumbItem v-for="(item, idx) in breadcrumb" :key="item.id">
    <span v-if="idx < breadcrumb.length - 1" @click="backToLevel(idx + 1)">{{ item.name }}</span>
    <span v-else>{{ item.name }}</span>
  </NBreadcrumbItem>
</NBreadcrumb>

<!-- 列表：用 v-for，不用 NDataTable -->
<div class="region-list">
  <div v-for="row in filteredList" :key="row.id" class="region-row" @click="onClickRow(row)">
    <span>{{ row.code }}</span>
    <span>{{ row.name }}</span>
    <NTag size="small">{{ row.region_type }}</NTag>
    <NButton size="tiny" @click.stop="deleteRow(row)">删除</NButton>
  </div>
</div>
```

**状态管理（面包屑模式）：**

```javascript
const breadcrumb = ref([])  // [{ id, name, type }]

// 点击行 → 进入子层级
function onClickRow(row) {
  breadcrumb.value.push({ id: row.id, name: row.name, type: row.region_type })
  loadDetail(row.id)       // 加载右侧详情
  loadCurrentLevel()        // 加载子列表
}

// 面包屑点击 → 回退
function backToLevel(index) {
  breadcrumb.value = breadcrumb.value.slice(0, index)
  loadCurrentLevel()
}

// 加载当前层级（根据 breadcrumb 深度自动切换）
async function loadCurrentLevel() {
  if (breadcrumb.value.length === 0) {
    // 根层级：加载国家
    currentList.value = await api.getRegionList({ region_type: 'COUNTRY' })
  } else {
    // 子层级：加载父节点的 children
    const parentId = breadcrumb.value[breadcrumb.value.length - 1].id
    currentList.value = await api.getRegionChildren(parentId)
  }
}
```

**虚拟滚动替代方案：** 如果列表可能很大（> 1000 项），用 CSS `overflow-y: auto` + 固定高度容器即可，无需 `virtual-scroll`。

**keepAlive 注意事项：**
- 子路由（非 Layout 级别）通常不会在后端菜单设置 `keepalive: true`
- 组件切换时会被完全销毁 → 重建，`onMounted` 正常触发
- **不要**依赖 `onActivated`（它只在 keep-alive 缓存组件激活时触发）
- 在 `onMounted` 中调用 `resetToRoot()` 确保每次进入都是干净状态

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

### 3.4 耗时任务全局弹窗进度展示

对于下载大文件、批量导入等耗时操作（> 30 秒），禁止在页面内嵌进度条（切换页面会销毁）。必须使用**全局任务进度面板**：

**架构：**

```
Pinia Store (taskProgress)     ← 跨页面状态
       ↓
TaskProgressPanel.vue          ← Layout 级 Teleport 渲染，右下角悬浮
       ↓
onFillGeonames()               ← 页面通过 store.startTask() 发起任务
       ↓
轮询 GET /xxx/progress         ← 后端写入进度状态文件
```

**Store 接口：**

```javascript
import { useTaskProgressStore } from '@/store/modules/taskProgress'

const store = useTaskProgressStore()
const taskId = store.startTask('填充行政区中文名', () => { /* retryHandler */ })
store.updateProgress(taskId, { progress: 30, message: '下载中...', phase: 'allCountries.zip' })
store.finishTask(taskId, '完成')
store.failTask(taskId, { message: '下载失败', detail: 'peer closed...' })
```

**任务面板特性：**
- 右下角悬浮，`<Teleport to="body">` 确保跨页面不销毁
- 支持多任务并行显示
- 可最小化为蓝色角标（显示运行中任务数）
- 失败任务显示红色进度条 + 错误详情 tooltip + **[重试]** 按钮
- 已完成任务 5 秒后自动移除

**后端进度状态文件：**

```python
# cache/geonames_progress.json
_progress = {
    "status": "idle",       # idle | downloading | parsing | bridging | done | error
    "phase": "",            # 当前阶段标识
    "progress": 0,          # 0-100
    "message": "",           # 用户友好描述
    "detail": "",            # 错误详情（前端 hover 展开）
}
```

同步提供 `GET /xxx/progress` 接口，前端每 2 秒轮询。

**实战案例一：有后端进度接口（真实进度）** — GeoNames 中文名下载

后端写入进度状态文件 → 前端轮询 `GET /fill-geonames/progress` → 显示真实百分比：

```javascript
// region/index.vue
function doStartGeonamesTask(proxy) {
  const store = useTaskProgressStore()
  const taskId = store.startTask('填充行政区中文名', () => doStartGeonamesTask(proxy))

  api.fillGeonames(true, proxy).catch(() => {})

  const timer = setInterval(async () => {
    const res = await api.getGeonamesProgress()
    const d = res.data || {}
    store.updateProgress(taskId, {
      progress: d.progress || 0,
      message: d.message || '',
      phase: d.phase || '',
    })
    if (d.status === 'done') {
      clearInterval(timer)
      store.finishTask(taskId, d.message)
    } else if (d.status === 'error') {
      clearInterval(timer)
      store.failTask(taskId, { message: d.message, detail: d.detail })
    }
  }, 2000)
}
```

**实战案例二：后端同步返回（模拟进度）** — 路网/边界下载

后端无进度接口、同步返回结果时，用 `setInterval` 模拟进度（10→85%），给用户"工作中"的反馈：

```javascript
// road-network/index.vue - onDownload()
const taskStore = useTaskProgressStore()
const nodeName = selectedNode.value.localName
  ? `${selectedNode.value.name}（${selectedNode.value.localName}）`
  : selectedNode.value.name
const taskId = taskStore.startTask(`路网下载: ${nodeName}`)

let simProgress = 10
const simTimer = setInterval(() => {
  if (simProgress < 85) {
    simProgress += 5
    taskStore.updateProgress(taskId, { progress: simProgress, message: '下载中...' })
  }
}, 800)

try {
  await api.downloadRoadNetwork({ ... })
  clearInterval(simTimer)
  taskStore.finishTask(taskId, '路网下载完成')
} catch (e) {
  clearInterval(simTimer)
  taskStore.failTask(taskId, { message: '路网下载失败', detail: errMsg })
}
```

**已接入全局面板的模块：**

| 模块 | 文件 | 进度类型 |
|------|------|----------|
| 行政区中文名填充 | `region/index.vue` | 真实进度（轮询后端） |
| 路网下载 (OSM) | `road-network/index.vue` | 模拟进度（同步返回） |
| 边界下载 (GADM) | `region-boundary/index.vue` | 模拟进度（同步返回） |

### 3.5 下载任务断点续传与重试

大文件下载（> 50MB）必须支持断点续传和重试，因为网络中断会导致已下载的部分浪费。

**核心原则：**
1. 下载中临时文件使用 `.tmp` 后缀
2. 失败时**不清除** `.tmp` 文件
3. 重试时发送 HTTP `Range: bytes={resume_pos}-` 头从断点续传
4. 下载完成后再 `os.rename(tmp, final)`
5. 后端错误写入进度状态文件（不抛异常），前端通过轮询感知失败

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
                # 服务器不支持续传，从头开始
                resume_pos = 0
                os.remove(tmp)
                # 重新请求不带 Range 头
                ...
            
            mode = "ab" if resume_pos > 0 else "wb"
            with open(tmp, mode) as f:
                async for chunk in resp.aiter_bytes():
                    f.write(chunk)
        
        os.rename(tmp, filepath)  # 原子操作
    except Exception as e:
        # .tmp 保留！不清除！
        logger.warning(f"下载中断: {e}（.tmp 文件已保留，下次可从断点续传）")
        raise
```

**前端重试流程：**

```javascript
function doStartTask() {
  const store = useTaskProgressStore()
  const taskId = store.startTask('填充行政区中文名', () => {
    doStartTask()  // 重试回调：递归调用自身
  })
  // 触发后端下载 + 轮询进度...
}
```

面板中失败任务自动显示 **[重试]** 按钮，点击 → `removeTask` → 调用 `retryHandler` → 重新开始（后端自动从断点续传）。

**实际实现：** `app/utils/geonames_downloader.py` — `_download_httpx()` 函数（140+ 行），完整覆盖上述 5 条原则。

**失败重试流程图：**

```
第1次下载：40/400MB 完成 → 网络中断
    .tmp 保留 (40MB)
    
用户点击 [重试]
    → Range: bytes=41943040-
    → 服务器返回 206 Partial Content
    → 从 40MB 续传，模式 "ab"（追加写）
    → 完成后 os.rename(.tmp → .zip)
    
后续导入：
    → 检测到 .zip 存在 → 直接读缓存 → 0 秒完成
```

### 3.6 大文件多线程分块下载

> **状态：设计草案，待实现。** 当前 GeoNames 下载使用单流 + 断点续传，已能满足需求。多线程分块作为未来超大文件（> 1GB）的优化方案。

**策略：**

```
文件总大小 N → 分成 M 块 (M = min(N / 50MB, 4)，最大 8)
每块独立线程下载 → Range: bytes=start-end
每块写入 .part0, .part1 ...
完成后按序合并所有 .part → 最终文件
清理 .part 文件
```

**参考实现骨架：**

```python
import asyncio
from concurrent.futures import ThreadPoolExecutor

async def download_chunked(url, filepath, chunk_count=4, chunk_size_mb=50, proxy=None):
    """多线程分块下载（结合断点续传）"""
    # 1. HEAD 请求获取 Content-Length
    async with httpx.AsyncClient(proxy=proxy) as client:
        resp = await client.head(url)
        total = int(resp.headers["content-length"])
    
    chunk_bytes = chunk_size_mb * 1024 * 1024
    parts = []
    for i in range(chunk_count):
        start = i * chunk_bytes
        end = min(start + chunk_bytes - 1, total - 1) if i < chunk_count - 1 else total - 1
        if start >= total:
            break
        parts.append((start, end, f"{filepath}.part{i}"))
    
    # 2. 并行下载每块（跳过已完成的 .part）
    async def _download_one(client, url, start, end, part_path):
        if os.path.exists(part_path):
            return  # 跳过已完成块
        headers = {"Range": f"bytes={start}-{end}"}
        async with client.stream("GET", url, headers=headers) as resp:
            with open(part_path + ".tmp", "wb") as f:
                async for chunk in resp.aiter_bytes():
                    f.write(chunk)
            os.rename(part_path + ".tmp", part_path)
    
    async with httpx.AsyncClient(proxy=proxy, timeout=600) as client:
        await asyncio.gather(*[
            _download_one(client, url, s, e, p) for s, e, p in parts
        ])
    
    # 3. 按序合并
    with open(filepath, "wb") as out:
        for _, _, part_path in parts:
            with open(part_path, "rb") as fp:
                out.write(fp.read())
            os.remove(part_path)
```

**每块的 `.part` 文件保留**，中断后只续传未完成的块。整体进度通过汇总各块完成度计算。线程数和块大小由 `system_config` 中的 `download_chunk_count` 和 `download_chunk_size_mb` 控制。

**适用场景：**
- GeoNames 数据下载（`allCountries.zip` ~400MB, `alternateNamesV2.zip` ~300MB）
- 路网 OSM 数据下载（可用 `osmnx` 内置下载，故优先级低于单流续传）
- 边界文件 GADM 下载

### 3.7 下载器统一读取系统代理配置

所有文件下载功能（GeoNames、GADM、OSMnx）必须从 `system_config` 表统一读取代理配置，而非各自硬编码。

**架构：**

```
系统管理 → 下载配置页面 → 用户填写代理 → 保存到 system_config 表
                                            ↓
每个下载器在执行 HTTP 请求前，从 system_config_controller.get_value("download_proxy") 读取
```

**三种下载器的代理注入方式：**

| 下载器 | HTTP 库 | 代理注入方式 |
|--------|---------|-------------|
| GeoNames | `httpx.AsyncClient` | `AsyncClient(proxy=proxy_url)` |
| GADM | `httpx.AsyncClient` | 同上，通过 `_get_proxy()` 辅助函数读取 |
| OSMnx | `requests`（线程池） | 下载前通过 `_set_proxy()` 设置 `HTTPS_PROXY` 环境变量 |

**OSMnx（线程池场景）的特殊处理：**

由于 OSMnx 通过 `run_in_executor` 在线程池中执行同步 `requests` 调用：

```python
# controller 层：下载前从系统配置读取代理
proxy_url = await system_config_controller.get_value("download_proxy", "")

def _set_proxy():
    if proxy_url:
        os.environ["HTTPS_PROXY"] = proxy_url
        os.environ["HTTP_PROXY"] = proxy_url

# 下载器方法签名：接受 _proxy_setup 回调
result = await loop.run_in_executor(None, functools.partial(
    OSMnxDownloader.download_by_boundary,
    ...,
    _proxy_setup=_set_proxy,
))
```

下载器内部第一行调用 `_proxy_setup()` 完成环境变量注入：

```python
@classmethod
def download_by_boundary(cls, ..., _proxy_setup=None):
    if _proxy_setup:
        _proxy_setup()  # 设置 HTTPS_PROXY
    ox = cls._import_osmnx()
    # ... 后续 osmnx → requests 调用自动走代理
```

**注意：**
- `httpx.AsyncClient` 本身在异步上下文中，可直接 `await system_config_controller.get_value(...)`
- `requests`（OSMnx）在线程池中执行，无法调用异步 ORM，必须通过闭包/回调在进入线程池前完成配置读取
- 代理配置为全局共用，所有下载模块统一从 `系统管理 → 下载配置` 页面管理

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

## 五、数据库迁移与部署

### 5.1 本地开发

```bash
# 生成迁移文件
make migrate       # 或 aerich migrate

# 应用迁移
make upgrade       # 或 aerich upgrade

# 重置数据库（删除所有表和迁移记录）
make clean-db      # 删除 migrations/ 和 db.sqlite3
```

**注意：** 每次修改模型后必须执行迁移，迁移文件应纳入版本控制并随部署包分发。

### 5.2 Docker 部署中的 SQLite 坑

- **数据库文件必须放在子目录中**（如 `data/db.sqlite3`），因为 Docker volume 挂载不存在的文件时会创建空**目录**，SQLite 无法打开
- `docker-compose.yml` 中 volume 使用目录挂载：`./data:/opt/app/data`，不要用文件挂载 `./db.sqlite3`
- 数据库路径在 `config.py` 中配置为 `BASE_DIR/data/db.sqlite3`
- 首次部署时容器内 `mkdir -p data` 确保目录存在

### 5.3 entrypoint.sh 中的迁移超时

`aerich upgrade` 可能因 Tortoise ORM 异步连接未关闭而卡住。用 `timeout` 包装：

```sh
set +e
timeout 120 aerich upgrade 2>/dev/null
AERICH_EXIT=$?
set -e
if [ $AERICH_EXIT -eq 124 ]; then
    echo "Migration timeout, continuing..."
fi
```

exit 124 = timeout 已杀死进程，迁移可能已完成，安全继续启动。

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
| 登录页/界面布局变形 | SVG logo 带有 `width="2048" height="2048"` 固定像素尺寸 | 移除 `width`/`height` 属性，只保留 `viewBox`，由 `unplugin-icons` (1em) + CSS 控制尺寸 |
| 白屏 loading 图标不是项目 logo | `loading.js` 硬编码了其他 SVG | 将项目 `logo.svg` 内联到 `loading.js`，颜色引用改为 `currentColor` |
| Docker 构建后 `VITE_BASE_API` 为空 | `.dockerignore` 中 `web/.env.*` 排除了 `.env.production` | 改为只排除 `web/.env.local` 和 `web/.env.*.local`，保留 `.env` 和 `.env.production` |
| `sqlite3.OperationalError: unable to open database file` | Docker volume 挂载不存在的文件时会创建空**目录** | volume 改用**目录挂载**（`./data:/opt/app/data`），数据库文件放入子目录 |
| `rm: cannot remove 'db.sqlite3': Device or resource busy` | 文件级 volume 挂载点在容器内无法删除 | 同上，改用目录级挂载 |
| `aerich upgrade` 执行完迁移后卡住不退出 | Tortoise ORM 异步连接未关闭 | 用 `timeout 120` 包装，捕获 exit 124 后继续启动 |
| `pip` 依赖冲突：`typing-extensions==4.12.2` vs `openai` 要求 `>=4.14` | `requirements.txt` 版本过时 | 用 `pip show` 确认实际安装版本后更新，与 `pyproject.toml` 保持同步 |
| NDataTable `virtual-scroll` + `flex-height` 搭配时行不渲染（列表空白） | 两者冲突：`virtual-scroll` 要求父容器 `overflow: hidden` + 明确高度；`flex-height` 让高度依赖弹性布局 | 去掉 `flex-height`，改用 `:max-height` 绑定固定值（如 `'calc(100vh - 430)'`），父容器设 `overflow: hidden` |
| NDataTable `row-props` 的 `onClick` 在虚拟滚动下不生效 | `virtual-scroll` 动态销毁/重建 DOM，`row-props` 事件绑定不稳定 | **改用 `v-for` + 自定义 `<div>` 列表**，直接 `@click="handler(row)"` 最可靠 |
| `:max-height="calc(100vh - 430)"` 报错 `Identifier directly after number` | Vue 模板将 `calc()` 当作 JS 表达式解析，`100vh` 不是合法标识符 | 加引号传字符串：`:max-height="'calc(100vh - 430)'"` |
| 页面钻入子层级后切换标签页，`onActivated` 未触发导致状态残留 | 子路由未设置 `keepAlive: true`（只有父路由有），组件被销毁重建而非缓存，`onActivated` 从不触发 | 在 `onMounted` 中调用重置函数即可，无需 `onActivated`；如需缓存则在后端菜单中为子路由设置 `keepalive: true` |
| 级联列表切换标签页后"卡在"旧页面 | 同上：组件销毁/重建正常，实际是其他渲染问题（如虚拟滚动坑） | 简化实现：用 `v-for` 替代 `NDataTable`，用面包屑 + 单区域列表替代多列布局 |
| 大文件下载中断后需从头开始 | 临时文件在异常时被删除 | 参考 3.5：失败保留 `.tmp` 文件，重试时用 `Range` 头断点续传 |
| 耗时任务切换页面后进度条消失 | 进度条嵌入页面内，路由跳转时组件销毁 | 参考 3.4：使用全局 TaskProgressPanel + Pinia store，Layout 级 Teleport 渲染 |
| 下载失败后前端无法感知错误 | 后端异常被 try/except 吞掉，前端无反馈 | 后端失败写进度状态文件 `_update_progress("error", ..., detail=...)`，前端轮询感知并显示重试按钮 |
| 大文件下载速度慢（单线程） | `urlretrieve` / 单流下载受单连接带宽限制 | 参考 3.6：多线程分块下载，`Range: bytes=start-end` 并行获取，完成后合并 |

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
11. **Docker**：SQLite 卷用目录挂载（`./data:/opt/app/data`），不用文件挂载 `.db.sqlite3`
12. **Docker**：`.dockerignore` 只排除 `web/.env.local`，不要排除 `.env.production`（含构建变量）
13. **入口**：`entrypoint.sh` 用 `timeout` 包装 `aerich upgrade`，防止异步连接卡死
14. **SVG**：logo/图标不加固定 `width`/`height`，只留 `viewBox`，由 `unplugin-icons` (1em) + CSS 控制
15. **依赖**：`requirements.txt` 新增依赖后，检查 `typing-extensions` 等共享依赖的版本兼容性
16. **级联列表**：逐层深入选择（如 国家→行政区→城市）用 `v-for` + 面包屑，**禁止** NDataTable + virtual-scroll + row-props 组合
17. **keepAlive**：子路由不会自动缓存，`onMounted` 即足够；不要依赖 `onActivated` 做重置
18. **耗时任务弹窗**：> 30 秒的耗时操作使用全局 TaskProgressPanel（Pinia store + Layout Teleport），不嵌入页面
19. **断点续传**：大文件下载（> 50MB）失败保留 `.tmp` 文件，重试用 `Range` 头续传
20. **分块下载**：超大文件（> 200MB）用多线程分块（`Range: bytes=start-end`），并行下载后合并
21. **下载失败通知**：后端失败写进度状态文件 `_update_progress("error", ..., detail=...)`，前端轮询感知并显示重试

---

请持续更新迭代此Skill, 但请注意以下事项：
1. 此Skill模块焦于**可复用的编程规范、架构模式、避坑指南**，不包含特定业务模块的实现细节。
2. 适用于前后端开发。
3. 具体的大模块，请单独生成模块后续功能新增及迭代Skill，客户的修改涉及到该模块时再加载Skill熟悉模块