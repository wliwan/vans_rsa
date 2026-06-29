# 需要收集的字段与交互设计

### 1. 基础信息

- 客户名称：单行文本输入。
- 试点区域名称：单行文本输入。
- 路网来源：单选（OSM下载、客户提供、其他），需要可填写其他的文本框（条件显示，选择“其他”时显示）。
- 潜在项目规模：单行文本输入。
- 客户背景信息: 多行文本输入。

### 2. 硬件方案（多选 + 自定义）

- 预设选项：
  - C40P + PBOX + G2
  - P4H + PBOX + M2
  - P2 + PBOX + G2
  - P2(三目) + PBOX + G2
  - P4C + PBOX + M2
  - C40P + M1N2.0 + P4H + M2
  - M1N2.0 + P4H + M2
  - C40P + M1N2.0 + G2
- 交互：每个预设使用复选框。下方添加“自定义方案”输入框（单行文本），并附一个“添加”按钮，点击后动态新增一个复选框+文本框的组合条目（名称可填入文本框），并可删除该条目。

### 3. AI项选择（分类折叠 + 全选/取消全选）

- 提供5个分类：城市管理AI、市政设施AI、极端天气AI、道路安全危害AI、道路路面质量AI（下分沥青路面、水泥路面、其他）。
- 每个分类为可折叠区块（默认展开），区块标题旁有“全选/取消全选”按钮，可一键操作该分类下的所有复选框，默认全部选中。
- 各分类内部列出具体选项（参考下方列表），需同时显示中文和英文名称（可中文为主，英文为副标签）。
- **列表内容**（严格使用以下数据）：

**城市管理AI列表**

| 中文名称                                 | English Name              |
| :--------------------------------------- | :------------------------ |
| 非机动车违停                             | Bike Misparked            |
| 非机动车倒地                             | Bike Fallen               |
| 占道经营                                 | Street Peddling           |
| 垃圾满溢                                 | Overflowing Trash Bin     |
| 路边垃圾堆放                             | Stacking Garbage          |
| 垃圾桶放置不规范                         | Misplaced Trash Bin       |
| 沿街晾挂                                 | Improper Street Hanging   |
| 高速行人                                 | Pedestrian on Expressway  |
| 小广告                                   | Flyer                     |
| 冒烟（焚烧垃圾）                         | Smoke (Trash Burning)     |
| 起火（焚烧垃圾）                         | Fire (Trash burning)      |
| 户外广告破损                             | Outdoor Ad Damage         |
| 临时广告破损                             | Temporary Ad Damage       |
| 电瓶车载人                               | Illegal E-bike Ride       |
| 共享单车摆放不整齐                       | Disorganized Shared Bikes |
| 液化石油气瓶外放                         | Exposed LPG Cylinder      |
| 废弃车辆                                 | Abandoned Vehicle         |
| 施工占道、脏乱差                         | Construction Mess         |
| 废弃家具                                 | Discarded Furniture       |
| 农用车、拖拉机、半截货车、电动三轮车载人 | Illegal Ride              |

**市政设施AI列表**

| 中文名称           | English Name                        |
| :----------------- | :---------------------------------- |
| 井盖损坏           | Manhole Cover Damage                |
| 道路平侧石破损     | Road Curb Damage                    |
| 伸缩装置损坏       | Expansion Joint Damage              |
| 排水设施损坏       | Drain Damage                        |
| 违章接坡           | Illegal Curb Ramp                   |
| 防撞柱破损、歪斜   | Bollard Damage                      |
| 隔离栅损坏         | Grid Barrier Damage                 |
| 护栏损坏           | Guardrail Damage                    |
| 车止石破损         | Damaged wheel stop / concrete block |
| 防撞桶破损         | Stop Stone Damage                   |
| 安全岛破损         | Safety Island Damage                |
| 工地围挡破损       | Construction Barrier Damage         |
| 立杆（线杆）破损   | Utility Pole Damage                 |
| 路灯（灯杆）破损   | Lamp Post Damage                    |
| 道路信息显示屏缺亮 | Screen Damage                       |
| 店招店牌破损       | Shop Sign Damage                    |
| 交通信号灯缺亮     | Traffic Light Damage                |
| 标牌（立杆类）破损 | Sign Damage                         |
| 减速带破损         | Speed Bump Damage                   |

**极端天气AI列表**

| 中文名称 | English Name  |
| :------- | :------------ |
| 积雪结冰 | Snow/Ice      |
| 大积水   | Water Ponding |
| 下雨天   | Rain          |
| 浓雾团雾 | Dense Fog     |
| 沙尘暴   | Sandstorm     |

**道路安全危害AI列表**

| 中文名称 | English Name      |
| :------- | :---------------- |
| 事故     | Accident          |
| 施工     | Construction      |
| 封路     | Road Closure      |
| 落石     | Fallen Rocks      |
| 车辆抛锚 | Vehicle Breakdown |
| 抛洒物   | Road Debris       |

**道路路面质量AI列表**

- 沥青路面子分类：| 中文名称 | English Name                 |
  | :------- | :--------------------------- |
  | 坑槽     | Pothole (Asphalt)            |
  | 沉陷     | Settlement (Asphalt)         |
  | 波浪拥包 | Washboard (Asphalt)          |
  | 拥包     | Hump (Asphalt)               |
  | 车辙     | Rutting (Asphalt)            |
  | 纵向线裂 | Longitudinal Crack (Asphalt) |
  | 横向线裂 | Transverse Crack (Asphalt)   |
  | 龟裂     | Alligator Crack (Asphalt)    |
  | 网裂     | Block Crack (Asphalt)        |
  | 剥落     | Raveling (Asphalt)           |
  | 啃边     | Edge Break (Asphalt)         |
  | 翻浆     | Bleeding (Asphalt)           |
  | 块状补丁 | Patch (Asphalt)              |
- 水泥路面子分类：| 中文名称         | English Name                     |
  | :--------------- | :------------------------------- |
  | 错台             | Faulting (Concrete)              |
  | 交叉裂缝和破碎板 | Cracks & Broken Slabs (Concrete) |
  | 坑洞             | Pothole (Concrete)               |
  | 拱胀             | Heave (Concrete)                 |
  | 沉陷             | Settlement (Concrete)            |
  | 纵向线裂         | Longitudinal Crack (Concrete)    |
  | 横向线裂         | Transverse Crack (Concrete)      |
  | 板角断裂         | Corner Break (Concrete)          |
  | 表面纹裂         | Surface Cracks (Concrete)        |
  | 层状剥落         | Delamination (Concrete)          |
  | 边角剥落         | Corner Spalling (Concrete)       |
  | 露骨             | Aggregate Exposure (Concrete)    |
- 其他子分类：| 中文名称 | English Name    |
  | :------- | :-------------- |
  | 路框差   | Misaligned Curb |

### 4. 客户需求列表（动态添加行）

- 提供一个表格或行列表，每行输入：需求名称、描述、优先级（下拉：高、中、低、暂不处理）。
- 下方有“添加需求”按钮，点击后在列表末尾增加一行，每行右侧有“删除”按钮。

### 5. POC计划列表（动态添加行）

- 每行输入：时间（日期类型）、行动（文本）、状态（下拉：已完成、进行中、未开始、挂起、取消）。
- 同样提供“添加计划”按钮和行删除功能。

### 6. API集成状态

- 是否提供API文档：单选（是/否）。
- 客户是否搭建起服务器：单选（是/否）。
- 是否正常通讯：单选（是/否）。
- 客户其他需求：文本域。

### 7. SIM卡情况

- 频段是否兼容：单选（是/否）。
- 预充值月流量数（30G）：数字输入。
- 是否是M2M：单选（是/否）。如果选“是”，条件显示：APN信息输入框、加入白名单状态（单选：已加入/未加入）。

### 8. 网络/代理服务

- 主服务器地址：文本输入, 默认值: 81.69.154.41。
- 直接访问延迟（ms）：数字输入。
- 是否启用代理服务器：单选（是/否）。如果选“是”，条件显示：代理服务器地址、与主服务器通讯延迟、与设备通讯延迟。

### 9. 设备管理系统列表（动态添加行）

- 每行可选择一个预设平台（下拉列表），或选择“自定义”。预设平台数据：
  - 新ceiba2平台: IP 124.221.242.141, 协议 N9M, 端口 5556, 账号 admin, 密码 Streamap2025+，设备端IP cbnew.xiangsu.work
  - alpha3.0平台: IP alpha3.xiangsu.work, 协议 905, 端口 21084, 账号 streamap, 密码 Streamap2025+，设备端IP alpha3.xiangsu.work
  - alpha2.0平台: IP 43.142.128.224, 协议 905, 端口 50007, 账号 streamap, 密码 Streamap2025++，设备端IP 43.142.128.224
  - 运维3.0平台: IP 118.89.187.31, 协议 N9M, 端口 21083, 账号 crocus, 密码 1qaz2WSX!，设备端IP 118.89.187.31
- 当选择预设时，自动填充服务器地址、协议、端口、账号、密码、设备端IP等字段（可见但不可编辑，或自动填值），默认所有预设都直接添加。
- 当选择“自定义”时，这些字段变为可编辑输入框，并额外提供“延迟”输入。
- 每行都有“删除”按钮，列表底部有“添加设备”按钮。

### 10. 待标注模型（多选）

- 使用复选框列出以下模型：

  1. 积水小模型
  2. 【道路类】六期26项+分类_1280
  3. 【城管类】五期25项+分类
  4. 【合并link】1234期检测+分类
  5. TSR (交通标志识别)
  6. 两轮车城管类【1】+【3】期模型97项
  7. 四轮车【7】期模型
  8. 四轮车城管模型
  9. 两轮车巡检类【2】+【4】期模型36项
  10. 树木过低
  11. 路灯缺亮
  12. 气象分类模型
  13. CG-152
  14. 施工封路事故模型

### 11. 其他参数

- POC预期通过率：百分比输入（数字+%）
- 轨迹点准确率：百分比输入
- 试点车型：文本输入
- 试点车数量：整数输入
- 预计POC里程（km）：数字输入
- 预估审核量：是否自动过审核（单选：是/否）。如果选“否”，显示“每日预估审核量”输入框（如2000条/天）。

### 12. 认证列表（动态添加行）

- 每行输入：机型、待认证项目(下拉: CE、CE-RED、CE-EMC、CE-LVD、E-Mark、RoHS、REACH、WEEE、FCC ID、TELEC、PSE、KC、RCM、NBTC、ANATEL、BIS、WPC。)、状态（下拉：待开始、已完成、进行中）、完成时间（日期）。
- 支持添加和删除行。

### 13. 其他

- 一个多行文本域，标签“其他”。

## 视觉效果与交互强化

- 使用书面填报风格：标签在上，控件在下，简洁边框，最大宽度600px居中，无阴影。
- 按钮悬停有颜色变化，最小高度40px。
- 移动端控件宽度100%，触摸友好。
- 对于动态列表，使用简洁的表格布局或卡片布局，每行内部字段水平排列（小屏时堆叠）。
- 条件显示字段用JavaScript实现，默认隐藏。