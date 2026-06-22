# 前端热更新指南

> 适用场景：后端代码未变，只改了前端（Vue 页面 / 组件 / 样式），不想重建整个 Docker 镜像。

## 原理

后端 FastAPI 和 Nginx 运行在**同一个 Docker 容器**内，Nginx 的静态文件根目录是 `/opt/VansRSA/web/dist/`。后端接收 zip 包后，直接解压替换该目录，Nginx 即时生效，零停机。

```
┌──────────────────────────────────────────┐
│  Docker 容器 (VansRSA)                   │
│                                          │
│  Nginx :80  ──读取──> /opt/VansRSA/      │
│                        web/dist/         │
│                          ↑              │
│  FastAPI :9999 ──写入──> (同目录)        │
│      ↑                                  │
│      │ POST /api/v1/deploy/update-frontend │
│      │                                  │
└──────┼──────────────────────────────────┘
       │
  ┌────┴────┐
  │ 浏览器   │ 上传 zip
  └─────────┘
```

## 方式一：独立上传页面（推荐）

**零依赖**——一个 HTML 文件即可，双击用浏览器打开，或通过 Nginx 提供。

### 本地打开

```bash
# 直接双击或用浏览器打开
firefox deploy/deploy-uploader.html
```

### 通过服务器访问

重新构建过前端后，可通过 Nginx 访问：

```
http://192.169.0.153:1110/deploy-uploader.html
```

### 操作流程

```
① 填服务器地址 → ② 用户名/密码登录 → ③ 选择 zip 文件 → ④ 点击上传 → ✅ 完成
```

页面支持拖拽 zip 文件到上传区域。

---

## 方式二：打包脚本 + API

### Step 1: 构建并打包

```bash
./package-frontend.sh
# 输出: dist_package/frontend-update-20260622-143000.zip
```

| 选项 | 说明 |
|---|---|
| `--no-build` | 跳过 `pnpm build`，使用已有 `web/dist/` |
| `-o NAME.zip` | 指定输出文件名 |

### Step 2: 上传

#### 用 curl

```bash
# 先获取 token
TOKEN=$(curl -s -X POST http://http://192.169.0.153:1110/api/v1/base/access_token \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"123456"}' | jq -r '.data.access_token')

# 上传 zip
curl -X POST http://http://192.169.0.153:1110/api/v1/deploy/update-frontend \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@dist_package/frontend-update-20260622-143000.zip"
```

#### 用 Swagger 文档

打开 `http://http://192.169.0.153:1110/docs` → 找到 `POST /api/v1/deploy/update-frontend` → Try it out → 选择文件上传。

#### 用 Python

```python
import requests

# 登录
resp = requests.post("http://http://192.169.0.153:1110/api/v1/base/access_token",
    data={"username": "admin", "password": "123456"})
token = resp.json()["data"]["access_token"]

# 上传
with open("dist_package/frontend-update-xxx.zip", "rb") as f:
    resp = requests.post("http://http://192.169.0.153:1110/api/v1/deploy/update-frontend",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": f})
print(resp.json())
```

---

## API 参考

### `POST /api/v1/deploy/update-frontend`

| 项目 | 说明 |
|---|---|
| 鉴权 | Bearer Token（JWT），需有 `/deploy` 路由权限 |
| Content-Type | `multipart/form-data` |
| 请求体 | `file` — zip 文件（`package-frontend.sh` 产出） |
| zip 结构 | 需包含 `dist/` 目录（内需有 `index.html`），支持一层外层目录 |
| 大小限制 | 无硬编码限制，取决于 Nginx `client_max_body_size` |

**成功响应：**

```json
{
  "code": 200,
  "msg": "前端已更新（197 个文件, 1.6 MB），Nginx 即时生效",
  "data": {
    "file_count": 197,
    "size_mb": 1.62,
    "target": "/opt/VansRSA/web/dist"
  }
}
```

**错误响应：**

```json
{"code": 400, "msg": "仅支持 .zip 格式"}
{"code": 400, "msg": "zip 包中未找到 dist/ 目录或 index.html"}
```

### 权限配置

首次使用需要在后台分配权限：

1. **菜单管理** → 确保当前角色有 API 权限
2. **角色管理** → 给角色勾选 `POST /api/v1/deploy/update-frontend` 接口
3. 如果使用 `admin` 账号（`is_superuser=True`），跳过所有权限检查

---

## 本地开发环境

如果是在本机直接跑（非 Docker），`update-frontend.sh` 仍然可用：

```bash
# 构建 + 直接替换本地 dist/
./update-frontend.sh
```

这也适用于通过 `docker cp` 手动更新容器的场景：

```bash
# 本地构建后手动推送到容器
./update-frontend.sh --no-build -c VansRSA
```

---

## 常见问题

**Q: 上传后页面没变化？**

检查浏览器缓存。Nginx 配置中 `index.html` 默认无强缓存，但 `assets/` 下的 JS/CSS 文件名带 hash，更新后 hash 会变，index.html 引用新 hash，强制刷新（Ctrl+F5）即可。

**Q: 上传的 zip 需要什么结构？**

```
✅ 正确                           ❌ 错误
zip                              zip
├── dist/                        ├── assets/
│   ├── index.html               ├── index.html
│   ├── assets/                  └── ...
│   └── ...                        (缺少 dist/ 包裹层)
└── update-frontend.ps1
    (不需要了，但存在也没关系)
```

`package-frontend.sh` 打包出来的 zip 就是正确结构。

**Q: 如何回滚？**

没有自动回滚。建议保留上一个 zip 文件，出问题时手动解压再上传一次。

**Q: 上传接口安全吗？**

- 需要 JWT 登录令牌
- 需要 `/deploy` 路由的 API 权限
- 已排除审计中间件（multipart 请求体不记录）
- 建议生产环境配置 Nginx `client_max_body_size` 限制上传大小
- **Nginx 默认 `client_max_body_size` 为 1MB**，压缩包超过 1MB 会报 413。部署时需在 `server` 块中设置 `client_max_body_size 1g;`（见 `deploy/web.conf`）

---

## 相关文件

| 文件 | 用途 |
|---|---|
| `package-frontend.sh` | 构建前端 + 打包 zip |
| `update-frontend.sh` | 本地/本机 Docker 直接更新 |
| `deploy/deploy-uploader.html` | 独立上传页面（可本地打开） |
| `web/public/deploy-uploader.html` | 同上（构建后通过 Nginx 提供） |
| `app/api/v1/deploy/deploy.py` | 后端上传接口 |
