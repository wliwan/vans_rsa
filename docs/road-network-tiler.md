# 路网瓦片服务方案

> 日期：2026-06-17（最后更新）
> 涉及文件：`app/api/v1/regions/road_network.py`、`app/controllers/region.py`、`app/utils/road_network_tiler.py`、`web/src/views/network/road-network-workbench/index.vue`、`app/utils/road_network_analyzer.py`

---

## 一、整体架构

```
前端 Leaflet                        后端 FastAPI
────────────                        ────────────
L.tileLayer  ──GET──→  /tiles/{id}/{z}/{x}/{y}.png
     ↑                        │
     │                   tile_router（独立 router，无 DependPermission）
     │                        │
     │                   RegionController.get_tile()
     │                        │
     │                   专用线程池 executor（8 workers）
     │                        │
     │                   RoadNetworkTiler.render_tile()
     │                        │
     │              ┌─────────┼─────────┐
     │              ▼         ▼         ▼
     │          磁盘 PNG   内存图缓存   冷加载
     │          (最快)   (STRtree+图)  (networkx)
     └──── PNG bytes ─────────────────────┘
```

---

## 二、API 层

| 端点 | 方法 | 鉴权 | 说明 |
|---|---|---|---|
| `/region/road-network/tiles/{network_id}/{z}/{x}/{y}.png?types=...` | GET | **无** | 瓦片服务（Leaflet 原生请求不带 JWT） |
| `/region/road-network/warm-cache?network_id=` | POST | **无** | 后台预热图缓存 |

### 路由注册

瓦片端点使用**独立的 `tile_router`**（`app/api/v1/__init__.py:39`），挂在 `/region/road-network` 前缀但**不加 `DependPermission`**，因为 Leaflet `L.tileLayer` 发起的原生 HTTP 请求不携带 JWT token。

路由文件：`app/api/v1/regions/road_network.py`

```python
# 主 CRUD 路由（带鉴权）
router = APIRouter()  # → 注册时加 dependencies=[DependPermission]

# 瓦片路由（无鉴权）
tile_router = APIRouter()  # → 注册时不加 DependPermission

@tile_router.get("/tiles/{network_id}/{z}/{x}/{y}.png")
async def get_tile(network_id, z, x, y, types: str = Query("")):
    ...
    png_bytes = await region_controller.get_tile(network_id, z, x, y, selected_types)
    return Response(content=png_bytes, media_type="image/png",
                    headers={"Cache-Control": "public, max-age=86400"})
```

### Controller 线程管理

Controller 通过**专用线程池**提交渲染任务（`RoadNetworkTiler._tile_executor`，8 workers），避免阻塞 FastAPI 的默认 executor：

```python
# app/controllers/region.py → get_tile()
png_bytes = await loop.run_in_executor(
    RoadNetworkTiler.get_executor(),  # ThreadPoolExecutor(8)
    functools.partial(RoadNetworkTiler.render_tile, file_path, network_id, z, x, y, selected_types),
)
```

---

## 三、渲染器 (`RoadNetworkTiler`)

文件：`app/utils/road_network_tiler.py`

### 依赖

| 库 | 用途 |
|---|---|
| `mercantile` | 瓦片坐标计算（`bounds`、`ul`、`xy`） |
| `shapely` | 空间索引 STRtree + 线段裁剪 |
| `Pillow` (PIL) | 256×256 PNG 渲染（`ImageDraw`） |
| `networkx` | 路网图加载（复用 `RoadNetworkAnalyzer._load_graph`） |

### 渲染流程

```
1. mercantile.bounds(x, y, z) → 瓦片经纬度边界 (west, south, east, north)
2. _load_graph_cached(file_path) → 获取 (networkx图, STRtree, edge_meta)
3. STRtree.query(box(边界), "intersects") → 相交边索引列表
4. types 过滤 → 所有拐点经纬度 → 像素坐标（墨卡托投影）
5. 逐段 Cohen-Sutherland 裁剪 → Pillow ImageDraw 折线渲染
6. Zoom 自适应线宽（Z8-Z20: 1-12px）
7. 保存磁盘缓存 + 返回 PNG bytes
```

> 边坐标优先使用原始 `geometry` 属性（Shapely LineString 完整坐标序列，含所有拐点）；若缺失则回退到两端点坐标。空间索引的 STRtree 也基于完整 LineString 构建，保证查询精度。

### 道路等级颜色映射

与前端 `highwayColors` 完全同步，覆盖 17 种道路类型：

```
motorway/motorway_link → (230, 74, 25)   # 高速公路
trunk/trunk_link       → (216, 67, 21)   # 国道
primary/primary_link   → (239, 108, 0)   # 主干道
secondary/secondary_link → (249, 168, 37) # 次干道
tertiary/tertiary_link → (67, 160, 71)   # 三级道路
residential/living_street → (30, 136, 229)
unclassified/road      → (158, 158, 158) # 未分类
service                → (117, 117, 117)
footway/cycleway/path/track/pedestrian → 各色
默认                    → (158, 158, 158)
```

### Zoom → 线宽映射

| Zoom | 0-7 | 8 | 9 | 10 | 11 | 12 | 13 | 14 | 15 | 16 | 17 | 18 | 19 | 20 |
|------|-----|---|---|----|----|----|----|----|----|----|----|----|----|----|
| px   | 0   | 1 | 1 | 2  | 2  | 3  | 4  | 5  | 6  | 7  | 8  | 9  | 10 | 12 |

Z0-Z7 直接返回透明空瓦片（瓦片覆盖范围太大，不渲染）。

---

## 四、三层缓存架构

| 层级 | 路径/位置 | 命中延迟 | 说明 |
|---|---|---|---|
| **1. 磁盘 PNG** | `uploads/tiles/{network_id}/{filter_key}/{z}/{x}/{y}.png` | ~0ms | 直接读文件返回，跨进程共享 |
| **2. 内存图缓存** | `_graph_cache`（LRU，最多 5 个） | <1ms | 含 networkx 图 + STRtree + edge_meta，线程安全 |
| **3. 冷加载** | 从 GPKG/GraphML 加载 | 数百ms-数秒 | 双重检查锁定，同一文件只加载一次 |

### 内存缓存并发安全 (`_load_graph_cached`)

```
快速路径：无锁 dict 读取缓存 → 命中直接返回（90%+ 请求走这里）

慢速路径（首次加载/缓存过期）：
  1. 获取 _cache_lock
  2. 双重检查（获取锁后再次读缓存，防止 TOCTOU）
  3. 检查 _load_events：若其他线程正在加载 → 释放锁 → Event.wait() 等待 → 重新获取锁 → 从缓存读
  4. 无其他线程加载 → 创建 Event 标记 → 释放锁 → 执行耗时的文件加载
  5. 加载完成后：获取锁 → LRU 驱逐（按时间戳） → 写入缓存 → Event.set() 通知等待线程
```

**LRU 驱逐**：`MAX_CACHED_GRAPHS = 5`，按最旧访问时间戳逐出。

### filter_key 安全处理

对 `selected_types` 参数净化：
- 只保留 `[a-z0-9_]+` 字符
- 单值长度限制 < 50 字符
- 净化结果 > 80 字符时用 MD5 哈希截断：`filter_{hash[:12]}`
- 空值 → `"all"`

防止目录遍历攻击和文件名过长。

---

## 五、前端使用

文件：`web/src/views/network/road-network-workbench/index.vue`

```javascript
// 瓦片 URL 动态构建
function buildTileUrl(networkId, types) {
  const safe = types
    .filter(t => typeof t === 'string' && t.length > 0 && t.length < 50)
    .map(t => t.replace(/[^a-z_]/g, ''))
  const params = safe.length ? `?types=${safe.join(',')}` : ''
  return `/region/road-network/tiles/${networkId}/{z}/{x}/{y}.png${params}`
}

// Leaflet 瓦片图层
roadTileLayer = L.tileLayer(url, {
  maxZoom: 19, minZoom: 8, opacity: 0.85,
  errorTileUrl: '',
}).addTo(map)
```

### 特点

- **即时响应**：`watch(selectedHighways)` 监听等级 Checkbox 变化，`updateTileLayer()` 替换瓦片 URL 参数，取消勾选即时隐藏
- **9 种底图**：Stadia (Outdoors/Dark/Toner/Imagery)、Yandex (Map/Satellite)、Bing Satellite、OpenStreetMap、Google Satellite
- **图层独立性**：底图 (`baseTileLayer`) 与路网瓦片 (`roadTileLayer`) 独立管理，切底图不移除路网
- **自适应视野**：路网分析完成后通过 GeoJSON bounds 自适应缩放
- **后台预热**：分析时调用 `POST /warm-cache` 后台加载图缓存

---

## 六、已知限制

1. ~~**边 geometry 仅用两个端点**~~ ✅ 已修复（2026-06-17）：`_load_graph_cached` 现在优先从边的 `geometry` 属性（Shapely LineString）提取完整拐点坐标序列；`render_tile` 改为逐段绘制折线。前提是源文件加载时保留了 geometry（`_load_gpkg` 同步修复）。

2. **无自动瓦片过期**：磁盘 PNG 缓存一旦写入不会自动清理，仅在调用 `RoadNetworkTiler.clear_cache(network_id)` 时手动清除。长期运行可能导致磁盘占用增长。

3. **内存图缓存有限**：LRU 最多缓存 5 个路网图。频繁切换路网文件时，旧的会被逐出并触发冷加载。

4. **低 Zoom 级全透明**：Z0-Z7 返回透明空瓦片，这些级别不会渲染任何路网数据。

5. **tile_router 无鉴权但无额外安全措施**：虽然通过 `network_id` 限制了文件范围，但理论上任何知道 `network_id` 的人都能访问瓦片。
