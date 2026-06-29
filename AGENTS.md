# Project Instructions

> 精简版：核心规则 + 速查表。详细模块指导见 `.codewhale/skills/` 下各 SKILL.md。

---

## 技术栈

| 层 | 技术 |
|---|---|
| 后端 | FastAPI + Tortoise ORM + Pydantic + Aerich |
| 前端 | Vue 3 + Vite + Naive UI + UnoCSS + pnpm |
| 鉴权 | JWT + argon2 (passlib) |

## 分层架构（后端）

```
API 路由层 (app/api/v1/)   → 参数/响应格式
控制器层 (app/controllers/) → 继承 CRUDBase，业务逻辑
Schema 层 (app/schemas/)   → Pydantic 校验
模型层 (app/models/)       → Tortoise ORM
```

## 统一响应格式

```python
Success(data={...})                                    # {"code":200,"msg":"OK","data":{...}}
SuccessExtra(data=list, total=100, page=1, page_size=10)  # 分页
Fail(code=400, msg="参数错误")                           # 错误
```

## 权限模型

```
User ──M2M──> Role ──M2M──> Menu + Api
```
- 超级管理员 (`is_superuser=True`) 跳过所有权限检查
- `v-permission` 指令值格式：`{method_lowercase}{path}`（如 `post/api/v1/user/create`）

---

## 后端强制规则

1. **控制器必须继承 `CRUDBase[Model, Create, Update]`**，发布单例 `xxx_controller = XxxController()`
2. **路由函数禁止直接操作 ORM**，所有数据库调用通过控制器
3. **路由 `summary` 必填中文描述**（写入审计日志）
4. **模型字符串字段必须有 `max_length` + `description`**，可搜索字段加 `index=True`
5. **路由注册加 `DependPermission`**，公开接口（如登录）不加
6. **同步阻塞操作用 `asyncio.to_thread()`** 包装，禁止在线程池中调用 Tortoise ORM
7. **审计中间件排除文件上传/二进制接口**（`app/core/init_app.py` 的 `exclude_paths`）

### CRUDBase 速查

```python
class XxxController(CRUDBase[XxxModel, XxxCreate, XxxUpdate]):
    def __init__(self):
        super().__init__(model=XxxModel)

xxx_controller = XxxController()
```
内置方法：`get(id)`, `list(page, page_size, search=Q(), order=[])`, `create(obj_in)`, `update(id, obj_in)`, `remove(id)`

### 模型模板

```python
class Xxx(BaseModel, TimestampMixin):
    name = fields.CharField(max_length=50, description="名称", index=True)
    class Meta:
        table = "xxx"
```

### Schema 模板

```python
class XxxCreate(BaseModel):
    name: str = Field(..., description="名称", example="示例")

class XxxUpdate(BaseModel):
    id: int
    name: str = Field(..., description="名称")
```

---

## 前端强制规则

1. **所有列表页必须用 `CrudTable`**，禁止手写 `NDataTable` + 手动分页
2. **增删改弹窗用 `useCRUD` 组合式函数**，表单内必须有 `<NForm ref="modalFormRef">`
3. **双面板布局（树+详情）用 flex + `overflow:hidden`**，禁止 `NSpace` 做外层容器
4. **`NTree` 必须加 `virtual-scroll`**，`@update:selected-keys` 回调取 `option[0]`
5. **`NTabs` + `NTabPane` 内容区滚动**：整条 flex 列链每层 `display:flex; flex-direction:column` + `min-height:0` + `overflow:hidden`；`.n-tab-pane` 默认 `display:block` 必须 `:deep()` 覆盖
6. **`NModal preset="card"` 按钮不显示**：必须用 `#footer` 插槽
7. **按钮权限用 `v-permission` 指令**，值为 `method+path`
8. **axios 拦截器必须处理 Blob**（`config.responseType === 'blob' || data instanceof Blob`）
9. **UnoCSS 字体**：全局 `html { font-size: 4px }` 使 rem 基准为 4px，每个页面必须在 `<style scoped>` 中用 `!important` + px 覆盖 `text-xs` 到 `text-xl`
10. **`CrudTable` 的 `row-key` 只接受 String（属性名）**，不能传函数

### CrudTable + useCRUD 模板

```vue
<template>
  <CommonPage title="模块管理">
    <template #action>
      <NButton @click="handleAdd">新建</NButton>
    </template>
    <CrudTable ref="$table" :columns="columns" :get-data="api.getXxxList" />
    <CrudModal>
      <NForm ref="modalFormRef" :model="form">
        <NFormItem label="名称"><NInput v-model:value="form.name" /></NFormItem>
      </NForm>
    </CrudModal>
  </CommonPage>
</template>

<script setup>
import { useCRUD } from '@/composables'
const $table = ref(null)
const { handleAdd, handleEdit, handleDelete, modalVisible, modalTitle, handleSave, modalFormRef, form } = useCRUD({
  name: '模块',
  initForm: { name: '' },
  doCreate: api.createXxx, doUpdate: api.updateXxx, doDelete: api.deleteXxx,
  refresh: () => $table.value?.handleSearch(),
})
</script>
```

### 双面板布局 CSS

```css
.dual-panel-layout { display:flex; height:calc(100vh - 180px); overflow:hidden; gap:8px; }
.left-panel { width:320px; flex-shrink:0; display:flex; flex-direction:column; overflow:hidden; }
.right-panel { flex:1; min-width:0; display:flex; flex-direction:column; overflow:hidden; }
.left-panel :deep(.n-card__content),
.right-panel :deep(.n-card__content) { flex:1; min-height:0; overflow:auto; }
```

---

## 异步与并发

- **同步阻塞操作** → `asyncio.to_thread(_sync_func)`
- **Tortoise ORM 禁止在线程池中调用** — 先 `await` 查询，再线程池处理其他事
- **耗时后端接口前端设 `{ timeout: 0 }`**

---

## 热更新（手动触发）

**不能自动触发** — 只有用户明确要求时才执行。

```bash
# 前端
bash hot-update.sh -p 'w570264649+'

# 后端
bash hot-update-be.sh -p 'w570264649+'
```

---

## 开发运维

```bash
./dev.sh start|stop|restart|status|logs [be|fe|tail]|log-clear|build
```

| 端口 | 地址 |
|---|---|
| 前端 | http://localhost:3100 |
| 后端 | http://localhost:9999 |
| API 文档 | http://localhost:9999/docs |

### 关键目录

| 目录 | 说明 |
|---|---|
| `app/api/v1/` | API 路由 |
| `app/controllers/` | 业务控制器 |
| `app/models/admin.py` | 所有 ORM 模型 |
| `app/schemas/` | Pydantic Schema |
| `app/core/` | 权限/JWT/中间件 |
| `web/src/views/` | 前端页面 |
| `web/src/components/common/` | 公共组件 |
| `web/src/composables/` | 组合式函数 |

---

## 数据库迁移

### 命令

```bash
make migrate   # aerich migrate — 生成迁移文件
make upgrade   # aerich upgrade — 应用迁移
make clean-db  # 删除 migrations/ 和 db.sqlite3
```

### 迁移编写规范（必须遵守，否则 Docker 部署重入报错）

`init_db()` 在启动时会先 `init_db(safe=True)` 基于当前模型建表（首次部署），再 `migrate()` + `upgrade()` 执行迁移。
若首次部署失败回退到 `aerich init-db` 后重启，迁移可能重入。因此**所有迁移必须幂等**。

**新增列（ALTER TABLE ADD）** — 必须用 `pragma_table_info` 预检：

```python
# ✅ 正确写法
from tortoise import BaseDBAsyncClient

async def upgrade(db: BaseDBAsyncClient) -> str:
    result = await db.execute_query(
        "SELECT COUNT(*) FROM pragma_table_info('表名') WHERE name='列名'"
    )
    if result[1][0][0] > 0:
        return "/* 列已存在，跳过 */"
    return """ALTER TABLE "表名" ADD "列名" 类型   /* 注释 */;"""
```

```python
# ❌ 错误写法 — 非幂等，重入必报 duplicate column
async def upgrade(db: BaseDBAsyncClient) -> str:
    return """ALTER TABLE "表名" ADD "列名" 类型;"""
```

**新建表（CREATE TABLE）** — 始终加 `IF NOT EXISTS`：

```sql
CREATE TABLE IF NOT EXISTS "表名" (...)  /* ✅ 幂等 */
CREATE TABLE "表名" (...)               /* ❌ 重入报 table already exists */
```

**模型字段 description 禁止改动**：Tortoise ORM 的 `description` 参数变更会被 aerich 检测为 schema 变化，SQLite 不支持 `ALTER COLUMN COMMENT`，会直接报错。若要改注释，只改 Schema/Pydantic 层的 `Field(description=...)`。

---

## 脚手架

```bash
python scripts/scaffold.py --name category --cn 分类 --fields "name:str:50:名称:true"
# 或交互式: python scripts/scaffold.py -i
# 或 JSON 配置: python scripts/scaffold.py --config scaffold_defs/gallery.json
```

**字段格式**: `字段名:类型:长度:描述:是否索引`（类型：str/int/float/bool/text/json/datetime）

生成后手动：`make migrate && make upgrade`，然后在后台菜单管理添加菜单。

---

## 新模块开发流程速查

1. `app/models/admin.py` 添加模型类 → 2. `app/schemas/xxx.py` 创建 Schema → 3. `app/controllers/xxx.py` 创建 Controller → 4. 导出到 `__init__.py` → 5. `app/api/v1/xxx/` 创建路由 → 6. 注册到 `app/api/v1/__init__.py` → 7. `make migrate && make upgrade` → 8. `web/src/api/index.js` 注册 API → 9. `web/src/views/{group}/{name}/index.vue` 创建页面 → 10. 后台菜单管理添加菜单

---

## 强制规则汇总（30 条）

1. 控制器继承 `CRUDBase`，路由加 `summary` 中文描述
2. 列表页用 `CrudTable`，禁止手写 `NDataTable` + 分页
3. 双面板用 flex + `overflow:hidden`，禁止 `NSpace`
4. `NTree` 加 `virtual-scroll`，回调取 `option[0]`
5. 同步阻塞 `asyncio.to_thread()`，Tortoise ORM 禁止进线程池
6. 耗时接口前端设 `timeout: 0`，加入审计中间件排除列表
7. 按钮权限 `v-permission`，值 `method+path`
8. 响应统一 `Success` / `SuccessExtra` / `Fail`
9. axios 拦截器必须处理 Blob 类型
10. 模型带 `description` 和 `index`
11. Docker SQLite 卷用目录挂载（`./data:/opt/app/data`），不用文件挂载
12. `.dockerignore` 只排除 `web/.env.local`，不排除 `.env.production`
13. `entrypoint.sh` 用 `timeout` 包装 `aerich upgrade`
14. SVG logo 不加固定 `width`/`height`，只留 `viewBox`
15. `NModal preset="card"` 用 `#footer` 插槽
16. 级联列表用 `v-for` + 面包屑，禁止 NDataTable + virtual-scroll + row-props
17. 子路由不依赖 `onActivated`，`onMounted` 足够
18. > 30 秒耗时操作用全局 TaskProgressPanel，不嵌入页面
19. 大文件下载（> 50MB）保留 `.tmp`，重试用 `Range` 续传
20. 超大文件（> 200MB）用多线程分块下载
21. 下载失败写进度状态文件，前端轮询感知
22. Leaflet 资源本地化到 `web/public/lib/leaflet/`
23. Leaflet 瓦片位置用 `getBoundingClientRect()`，img 用 `el.querySelector('img')`
24. 图层导出含跨域瓦片用 `html-to-image`，纯同源用 Canvas
25. PNG 元数据写入 JSON（Pillow `PngInfo`）
26. UnoCSS 字体：每个页面 `<style scoped>` 中用 px + `!important` 覆盖 `text-*` 类，禁止改全局 `html` 基准
27. `CrudTable` 的 `row-key` 只接受 String（属性名），不能传函数
28. 热更新不能自动触发，仅用户明确要求时执行
29. Tab 内容区滚动：flex 列链每层 `display:flex;flex-direction:column` + `min-height:0` + `overflow:hidden`
30. Survey AI 调用用 openai SDK + `asyncio.to_thread()`
31. **所有 AI 调用必须从 AIProxy 读取 `max_tokens` 参数**，禁止硬编码。AIProxy 模型已内置 `max_tokens` 字段（默认 16384），新 AI 功能通过 `proxy.max_tokens or 16384` 获取

---

## 常见错误速查

| 现象 | 原因 | 解决 |
|---|---|---|
| 树节点选中报 422 | `option` 是数组 | 取 `option[0]` |
| 页面右侧内容溢出 | 用了 `NSpace` 或未设 overflow | flex + `overflow:hidden` |
| 上传报 `UnicodeDecodeError` | 审计中间件解析了 multipart | 加入 `exclude_paths` |
| 前端请求超时 | 未设 `timeout: 0` | 添加 `{ timeout: 0 }` |
| 异步接口卡死 | 同步阻塞未进线程池 | `asyncio.to_thread()` |
| ORM 在线程中报错 | 线程中调了 ORM | 先 `await` 查询，再线程池 |
| `CrudModal` 保存无反应 | 缺少 `<NForm ref="modalFormRef">` | 添加 ref 绑定 |
| `NModal` 按钮不显示 | `preset="card"` 未用 footer 插槽 | 使用 `#footer` 插槽 |
| 文件下载返回 HTML | Blob 被拦截器错误处理 | 先判断 `data instanceof Blob` |
| `import.meta.env` 模板报错 | Vue 模板不支持 | `<script>` 中用 `computed` |
| SVG logo 布局变形 | 固定 `width/height` | 只保留 `viewBox` |
| Docker `VITE_BASE_API` 为空 | `.dockerignore` 排除了 `.env.production` | 只排除 `web/.env.local` |
| SQLite 无法打开 | Docker volume 文件挂载创建空目录 | 目录挂载 `./data:/opt/app/data` |
| `aerich upgrade` 卡住 | Tortoise 异步连接未关闭 | `timeout 120` 包装 |
| 迁移报 `duplicate column` / `table already exists` | 迁移非幂等 + `init_db` 重入 | `pragma_table_info` 预检 / `IF NOT EXISTS` |
| 大文件下载中断 | 异常时删除了 `.tmp` | 保留 `.tmp`，重试用 `Range` 续传 |
| 耗时任务切页后进度消失 | 进度条嵌入页面 | 用全局 TaskProgressPanel + Pinia Store |
| UnoCSS 字体极小 | 全局 `html { font-size: 4px }` | scoped 中 `!important` + px 覆盖 |
| Tab 内容区无法滚动 | flex 链断裂 | 3 层修复：`:deep(.n-tab-pane)`, `.n-spin-container`, 双栏容器 |
| CodeMirror 高度 0 | `.CodeMirror` 不自动填充 | `cmInstance.getWrapperElement().style.height='100%'` + CSS `!important` |
| `CrudTable` checkbox 无法选中 | `row-key` 传了函数 | 传属性名字符串 |
| AI 生成内容截断/拼接错误 | `max_tokens` 硬编码 8192 过小 | 从 AIProxy 读取 `max_tokens`，默认 16384 |

---

## 后端模块速查

| 模块 | 路由 | 控制器 |
|---|---|---|
| 用户管理 | `/user` | UserController |
| 角色管理 | `/role` | RoleController |
| 菜单管理 | `/menu` | MenuController |
| API 管理 | `/apis` | ApiController |
| 部门管理 | `/dept` | DeptController |
| Skill 管理 | `/skill` | SkillController |
| AI 代理 | `/ai-proxy` | AIProxyController |
| 系统配置 | `/sysconfig` | SystemConfigController |
| 国际化 | `/i18n` | I18nController |
| 工作区 | `/workspace` | WorkspaceController |
| 文档 | `/document` | DocumentController |
| 报告 | `/report` | ReportController |
| 路网区域 | `/region` | RegionController |
| 路网素材 | `/road-material` | RoadMaterialController |
| 轨迹 | `/track` | TrackController |
| 病害 | `/defect` | DefectController |
| 车辆 | `/vehicle` | VehicleController |
| 调研问卷 | `/survey` | SurveyController |

---

## Cache Stability

新上下文追加到末尾，不重排已有内容。不重复读同一文件。

---

*此文件由原 AGENTS.md 精简而来。详细模块指导（路网数据中心、调研问卷等）见 `.codewhale/skills/` 目录。*
