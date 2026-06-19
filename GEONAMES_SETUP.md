# GeoNames 中文地名数据首次下载指南

## 背景

行政区管理模块的 STATE（一级行政区）和 CITY（二级行政区）默认只有英文名。
初次使用时需要从 [GeoNames](https://www.geonames.org/) 下载中文地名数据来填充 `local_name` 字段。

## 首次下载

### 方式一：CLI（推荐）

在项目根目录执行：

```bash
python -m app.utils.geonames_downloader --force
```

- 会从 `download.geonames.org` 下载两个文件（共计约 **700MB**）
  - `allCountries.zip`（~400MB）
  - `alternateNamesV2.zip`（~300MB）
- 下载 + 解析 + 桥接 + 写入数据库，总计约 **3–10 分钟**（视网络速度）
- 首次运行生成离线缓存 `cache/geonames_zh_map.json`，后续导入秒级复用
- 若不想阻塞终端，可后台运行：

```bash
nohup python -m app.utils.geonames_downloader --force > geonames.log 2>&1 &
tail -f geonames.log   # 查看进度
```

### 方式二：API 接口

调用区域管理模块的填充接口（适合已在运行的环境中）：

```
POST /api/v1/region/fill-geonames?force_download=true
```

> ⚠️ 此接口会阻塞请求 3–10 分钟，前端调用时务必设置 `timeout: 0`，或使用 curl / Postman 触发。

## 后续使用

- 首次下载完成后，每次调用 `POST /api/v1/region/import`（导入国家数据）时会自动检测离线缓存并回填 STATE/CITY 的中文名。
- 如需强制刷新缓存（GeoNames 数据更新时）：
  ```bash
  python -m app.utils.geonames_downloader --force
  ```

## 覆盖率

- 通过**英文名 + 国家代码**桥接，预期覆盖率约 **60–80%**
- 覆盖率取决于 GeoNames 中是否收录了对应行政区的中文名
- 中国的 34 个省/自治区/直辖市 + ~370 个地级市基本可全覆盖

## 文件清单

| 文件 | 说明 |
|------|------|
| `app/utils/geonames_downloader.py` | 下载器 + CLI 入口 |
| `cache/allCountries.zip` | 缓存（下载后保留，下次跳过） |
| `cache/alternateNamesV2.zip` | 缓存（下载后保留，下次跳过） |
| `cache/geonames_zh_map.json` | 离线映射文件（核心缓存） |
| `app/utils/country_zh_map.json` | 国家中文名对照表（COUNTRY 级别用，无需下载） |

## 注意事项

- 确保外网能访问 `download.geonames.org`
- 确保磁盘空间 > 2GB（zip + 临时解压文件）
- 如果下载中断，删除 `cache/allCountries.zip` 和 `cache/alternateNamesV2.zip` 后重试
- 不需要版本控制这些大文件，建议在 `.gitignore` 中已忽略 `cache/`
