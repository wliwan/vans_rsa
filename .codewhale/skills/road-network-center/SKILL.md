# 路网数据中心（Road Network Data Center）开发指导

## 模块概述

路网数据中心是 Vue-FastAPI-Admin 中的大型数据管理模块，负责全球地理行政区划及路网数据的管理。包含三个子模块：

| 子模块 | 状态 | 说明 |
|---|---|---|
| 全球国家及行政区管理 | ✅ 已实现 | 国家/行政区/城市三级管理 |
| 全球国家及行政区边界文件管理 | ✅ 已实现 | GeoJSON/KML 边界文件下载/上传/导出 |
| 全球国家及行政区路网文件管理 | ✅ 已实现 | OSMnx 下载路网（按地名/按边界），GraphML 导入导出 |

---

## 核心数据模型

### Region（自引用树）

所有子模块共用 `Region` 表，通过 `region_type` + `parent_id` 自引用形成树：

```
COUNTRY (parent_id=null)
  └── STATE (parent_id=国家.id)
       └── CITY (parent_id=行政区.id)
```

**关键字段：**

| 字段 | 类型 | 说明 |
|---|---|---|
| name | VARCHAR(200) | 名称（中文或英文） |
| code | VARCHAR(20) | ISO 代码（国家用 alpha-2，如 CN） |
| iso_alpha2 | VARCHAR(2) | ISO 3166-1 alpha-2 |
| iso_alpha3 | VARCHAR(3) | ISO 3166-1 alpha-3 |
| iso_numeric | VARCHAR(3) | ISO 3166-1 numeric |
| region_type | ENUM (COUNTRY/STATE/CITY) | 层级类型 |
| parent_id | FK → region.id | 父级引用 |
| capital | VARCHAR(200) | 首都/首府 |
| population | BIGINT | 人口 |
| area | FLOAT | 面积 (km²) |
| latitude / longitude | FLOAT | 经纬度 |
| timezone | VARCHAR(100) | 时区 |
| is_active | BOOL | 是否启用 |

### ISO 3166 数据导入

使用 `pycountry` 库批量导入三级数据：

```
pycountry.countries     → COUNTRY（国家，~249 条）
pycountry.subdivisions  → 按 parent_code 区分：
                          无 parent_code → STATE（一级行政区，~3590 条）
                          有 parent_code → CITY（二级行政区，~1456 条）
```

```python
# 安装
pip install pycountry

# 导入（API: POST /api/v1/region/import）
# 返回格式:
# {
#   "created_country": 249, "updated_country": 0,
#   "created_state": 3590, "created_city": 1456,
#   "skipped_state": 0, "skipped_city": 0
# }
```

> **注意**：`pycountry.subdivisions` 仅包含 ISO 3166-2 定义的行政区划，不包含所有城市。二级行政区（有 `parent_code` 的）如中国的地级市会被映射为 CITY 类型。更多城市数据需通过其他数据源（如 GeoNames）补充导入。

---

## API 接口

### 全球国家及行政区管理（已实现）

| 方法 | 路径 | 功能 |
|---|---|---|
| GET | `/api/v1/region/tree` | 完整树结构（用于前端 NTree） |
| GET | `/api/v1/region/children?parent_id=` | 获取某节点的直接子节点 |
| GET | `/api/v1/region/get?region_id=` | 单条详情 |
| GET | `/api/v1/region/list?name=&code=&region_type=` | 多字段筛选查询 |
| POST | `/api/v1/region/create` | 新增区域 |
| POST | `/api/v1/region/update` | 更新区域 |
| DELETE | `/api/v1/region/delete?region_id=` | 删除（含级联子区域） |
| POST | `/api/v1/region/import` | pycountry 批量导入国家 |
| POST | `/api/v1/region/clear` | 全部清空 |
| POST | `/api/v1/region/export` | 导出 JSON（支持 ALL/STATE/CITY 级别） |
| POST | `/api/v1/region/batch-update` | 批量更新 |

### 前端 API 注册

```javascript
// web/src/api/index.js
// regions
getRegionTree: () => request.get('/region/tree'),
getRegionChildren: (parent_id) => request.get('/region/children', { params: { parent_id } }),
getRegionById: (region_id) => request.get('/region/get', { params: { region_id } }),
getRegionList: (params = {}) => request.get('/region/list', { params }),
createRegion: (data = {}) => request.post('/region/create', data),
updateRegion: (data = {}) => request.post('/region/update', data),
deleteRegion: (params = {}) => request.delete('/region/delete', { params }),
importRegions: () => request.post('/region/import', {}, { timeout: 0 }),
clearRegions: () => request.post('/region/clear', {}, { timeout: 0 }),
exportRegions: (data = {}) => request.post('/region/export', data),
batchUpdateRegions: (data = {}) => request.post('/region/batch-update', data),
```

> **注意**：
> - `getRegionById` 和 `getRegionChildren` 接受单个值（非对象），内部通过 `{ params: { key: value } }` 传递给 axios。
> - `importRegions` 和 `clearRegions` 涉及大量数据操作，必须设置 `{ timeout: 0 }` 关闭超时限制，防止请求被中断。

---

## 前端页面布局规范

### 树状双面板布局（已采用）

路网数据中心的页面使用**左侧树 + 右侧详情**的双面板布局：

```
┌──────────────────────────────────────────────┐
│  [导入] [清空]  操作按钮区                      │
├──────────────┬───────────────────────────────┤
│  区域树       │  详情面板                       │
│  (NTree)     │  - 字段展示（只读）               │
│  320px       │  - [编辑] [新增子级] [导出] [删除] │
│              │  - 子节点列表（NDataTable）       │
└──────────────┴───────────────────────────────┘
```

**关键组件：**

- `NTree`：展示树结构，`key-field="id"` `label-field="label"` `children-field="children"`，**必须添加 `virtual-scroll` 避免大量节点撑破容器**
- `NCard`：左右两个卡片容器，需配合 flex 布局 + `overflow: hidden` 限制溢出
- `NDataTable`：右侧子节点列表（非 CrudTable，因为无需分页/搜索）
- `NModal`：新增/编辑弹窗

**容器布局要点（防止内容溢出）：**

> **⚠️ 重要**：`NSpace` 不传递高度约束，外层必须使用普通 `div` + `display: flex` 布局。NCard 需设置 `display: flex; flex-direction: column; overflow: hidden`，并用 `:deep(.n-card__content)` 穿透设置 `flex: 1; min-height: 0; overflow: auto`。

```html
<!-- 外层容器：flex row，固定高度，overflow: hidden 阻止溢出 -->
<div class="region-layout">
  <!-- 左侧面板：固定宽度，flex column -->
  <NCard class="left-panel">
    <NTree virtual-scroll ... />
  </NCard>
  <!-- 右侧面板：flex: 1 占满剩余空间 -->
  <NCard class="right-panel">
    <!-- 内容 -->
  </NCard>
</div>
```

```css
.region-layout {
  display: flex;
  height: calc(100vh - 180px);
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
/* 穿透 NCard 内部结构，让内容区可滚动 */
.left-panel :deep(.n-card__content),
.right-panel :deep(.n-card__content) {
  flex: 1;
  min-height: 0;
  overflow: auto;
}
/* 树节点长文本截断 */
.left-panel :deep(.n-tree-node-content__text) {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
```

**树数据结构（后端返回）：**

```json
[
  {
    "id": 1,
    "label": "中国",
    "code": "CN",
    "region_type": "COUNTRY",
    "children": [
      {
        "id": 2,
        "label": "北京",
        "code": "CN-BJ",
        "region_type": "STATE",
        "children": [
          {"id": 3, "label": "东城区", "code": "CN-BJ-DC", "region_type": "CITY"}
        ]
      }
    ]
  }
]
```

**关键事件处理：**

> **⚠️ 重要**：Naive UI NTree 的 `@update:selected-keys` 事件签名是 `(keys: Array, option: Array<TreeOption>)`，**第二个参数是选中节点的数组**，不是单个对象。必须取 `option[0]` 才能拿到实际节点。

```javascript
// 树节点选中 → 加载详情 + 子节点列表
// ⚠️ option 是数组，取 option[0] 拿到实际节点
function onNodeSelect(keys, option) {
  if (keys.length === 0) {
    selectedNode.value = null
    childrenList.value = []
    return
  }
  const node = Array.isArray(option) ? option[0] : option  // 防御性取第一个
  selectedNode.value = node
  loadNodeDetail(node.id)   // GET /region/get?region_id=...
  loadChildren(node.id)     // GET /region/children?parent_id=...
}
```

---

## 待实现子模块指导

### 全球国家及行政区边界文件管理 ✅

**数据模型**（`app/models/admin.py`）：

```python
class RegionBoundary(BaseModel, TimestampMixin):
    region = fields.ForeignKeyField("models.Region", related_name="boundaries")
    file_name = fields.CharField(max_length=200, description="文件名")
    file_type = fields.CharEnumField(BoundaryType)  # GEOJSON / KML / SHP
    file_path = fields.CharField(max_length=500, description="存储路径")
    file_size = fields.BigIntField(null=True, description="文件大小(字节)")
    srid = fields.CharField(max_length=20, null=True, default="EPSG:4326", description="坐标系")
    download_status = fields.CharEnumField(BoundaryStatus)  # PENDING/DOWNLOADING/SUCCESS/FAILED
    error_message = fields.CharField(max_length=500, null=True, description="错误信息")
    is_active = fields.BooleanField(default=True)
```

**API 接口：**

| 方法 | 路径 | 功能 |
|---|---|---|
| GET | `/region/region-boundary/status?region_id=` | 检查边界文件下载状态及列表 |
| POST | `/region/region-boundary/download` | 从 GADM 下载边界 GeoJSON |
| POST | `/region/region-boundary/upload` | 上传边界文件（multipart） |
| DELETE | `/region/region-boundary/delete?boundary_id=` | 删除单个边界文件 |
| DELETE | `/region/region-boundary/clear?region_id=` | 清除区域所有边界文件 |
| GET | `/region/region-boundary/download-file?boundary_id=` | 导出/下载边界文件（FileResponse） |

**下载机制**：通过 GADM (`gadm.org`) 获取全球行政区边界 GeoJSON 数据，按 ISO Alpha-3 国家代码 + 行政级别下载。数据存储到 `uploads/boundaries/` 目录。请求必须设置 `{ timeout: 0 }`（GADM 文件较大，可能需要 2 分钟以上）。

**下载器**：`app/utils/gadm_downloader.py` — `GADMDownloader` 类，封装 GADM 4.1 GeoJSON API 调用。

**映射关系**：COUNTRY → GADM level 0，STATE → level 1，CITY → level 2。下载时先向上追溯找到所选区域所属国家的 `iso_alpha3`，再根据 `region_type` 确定级别。

### 全球国家及行政区路网文件管理 ✅

**数据模型**（`app/models/admin.py` — `RoadNetwork`）：

```python
class RoadNetwork(BaseModel, TimestampMixin):
    region = fields.ForeignKeyField("models.Region", related_name="road_networks")
    file_name = fields.CharField(max_length=200)
    file_type = fields.CharEnumField(RoadNetworkType)  # GRAPHML / OSM / GPKG / SHP
    file_path = fields.CharField(max_length=500)
    file_size = fields.BigIntField(null=True)
    node_count = fields.BigIntField(null=True)    # 路网节点数
    edge_count = fields.BigIntField(null=True)    # 路网边数
    srid = fields.CharField(max_length=20, null=True, default="EPSG:4326")
    download_mode = fields.CharField(max_length=50, null=True)  # boundary / name
    download_status = fields.CharEnumField(RoadNetworkStatus)   # 下载状态
    error_message = fields.CharField(max_length=500, null=True)
    is_active = fields.BooleanField(default=True)
```

**API 接口：**

| 方法 | 路径 | 功能 |
|---|---|---|
| GET | `/region/road-network/status?region_id=` | 检查路网下载状态及列表 |
| POST | `/region/road-network/download` | 从 OSM 下载路网（body: `{region_id, mode, file_type}`） |
| POST | `/region/road-network/upload` | 上传路网文件 |
| DELETE | `/region/road-network/delete?network_id=` | 删除单个路网文件 |
| DELETE | `/region/road-network/clear?region_id=` | 清除区域所有路网文件 |
| GET | `/region/road-network/download-file?network_id=` | 导出/下载路网文件 |

**下载器**：`app/utils/osmnx_downloader.py` — `OSMnxDownloader`

**两种下载模式**：

| 模式 | `mode` 参数 | 原理 |
|---|---|---|
| 边界模式 | `"boundary"` | 读取该区域已有的 `RegionBoundary` GeoJSON → 提取 polygon → `ox.graph_from_polygon()` |
| 地名模式 | `"name"` | 构造 "区域名, 国家名" → `ox.graph_from_place()` |

保存格式为 GraphML，统计 `node_count` 和 `edge_count`。需要安装 `pip install osmnx`。

---

## 开发规范

1. **树数据结构**：`get_tree()` 返回 `{id, label, code, region_type, children}` 格式，适配 NTree 组件
2. **导出**：使用 `POST /export` 接收 `{country_id, level}` 参数，返回 JSON 数据，前端用 Blob 下载
3. **删除**：删除父节点时需级联删除所有子节点（Tortoise ORM 的 `ON DELETE CASCADE` 处理）
4. **前端参数**：`getRegionById` 和 `getRegionChildren` 直接传值（非对象），内部通过 `{ params: { key: value } }` 传递
5. **双面板布局**：国家及行政区管理页面使用树+详情面板，区别于标准 CRUD 表格页面
6. **NTree 事件参数**：`@update:selected-keys` 的第二个参数是 `Array<TreeOption>`（选中节点数组），不是单对象，必须用 `option[0]` 或 `Array.isArray(option) ? option[0] : option` 取出实际节点后再访问 `.id` 等属性。直接用 `option.id` 会得到 `undefined`，导致 API 请求缺少必填查询参数而报 422
7. **容器防溢出**：外层必须用 `div` + `display: flex`（不可用 `NSpace`），NCard 设置 `display: flex; flex-direction: column; overflow: hidden`，用 `:deep(.n-card__content)` 穿透设置 `flex: 1; min-height: 0; overflow: auto`。NTree 必须加 `virtual-scroll`，长文本节点用 `:deep(.n-tree-node-content__text)` 添加 `overflow: hidden; text-overflow: ellipsis; white-space: nowrap`
8. **后台耗时操作**：涉及大量数据处理的后台请求（如导入、清空、同步），前端 axios 调用必须设 `{ timeout: 0 }` 关闭超时限制。默认 12s 超时不足以完成 ~5000 条数据的导入操作
9. **Vue 模板限制**：`import.meta.env` 和 `localStorage` 等浏览器/构建时 API 不能直接写在 Vue template 表达式中（会报 `import.meta may appear only with 'sourceType: "module"'`），必须在 `<script setup>` 中用 `computed` 定义好再传给模板
10. **NTree 搜索**：搜索框放在 NCard 默认插槽中（树的上方，不用 `#header-extra`），绑定 `:pattern` + `:filter` 实现大小写不敏感过滤。Naive UI 自动展开匹配节点的父级路径。关键代码：

    ```html
    <NInput v-model:value="treePattern" placeholder="搜索区域名称..." clearable size="small" />
    <NTree
      :pattern="treePattern"
      :filter="(pattern, node) => !pattern || String(node.label||'').toLowerCase().includes(String(pattern).toLowerCase())"
      ...
    />
    ```

    `filter` 函数确保仅 `label` 字段参与匹配，空 pattern 时显示全部节点。
11. **Blob 响应拦截**：axios 响应拦截器中必须先判断 `config.responseType === 'blob'` 或 `data instanceof Blob`，对 Blob 响应直接 `return Promise.resolve(response)`（透传原始 response），否则 `data?.code !== 200` 会把 Blob 误判为错误响应导致文件下载失败
12. **异步非阻塞**：所有耗时同步操作（如 OSMnx 下载、大文件 I/O）必须通过 `asyncio.get_running_loop().run_in_executor(None, fn)` 放入线程池执行，避免阻塞事件循环。`httpx.AsyncClient` 和 Tortoise ORM 的 `await` 操作本身是异步的无需额外处理。若一个请求卡在同步操作上，asyncio 事件循环被阻塞，**所有其他请求也会卡死**
