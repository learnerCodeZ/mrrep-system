# 使用指南 Usage Guide

> `mrrep_bridge` 的日常使用：一键启动、三模式、twist_mux 手动接管、WebRop 操控、排错。
> 入门看 [README](../README.md)，架构看 [architecture.md](architecture.md)，本文讲"怎么用"。

---

## 0. 前置（一次性，确认都满足）

- **机器人 PC**：Ubuntu 20.04 + ROS Noetic
- **小车仓库** `~/EP_navigation_Ros1` 已编译、已建好地图（`src/rm_ep_navigation/maps/` 下有文件夹）
- **`mrrep_bridge`** 编译在独立工作区 `~/mrrep_ws`（overlay 在小车工作区上）：`source ~/mrrep_ws/devel/setup.bash` 后 `rospack find mrrep_bridge` 有输出
- **装了 twist_mux**：`sudo apt install -y ros-noetic-twist-mux`
- **小车连接**：EP 用 USB 线连机器人 PC（`rndis`，仓库默认模式），EP 已开机
- **WebRop** 跑在开发 PC（Windows），和机器人 PC 同一局域网

## 1. 一键启动 `start.launch`

一条命令，`mode` 选模式，**所有模式都自动起 rosbridge(:9090) + twist_mux**。

```bash
source ~/mrrep_ws/devel/setup.bash
roslaunch mrrep_bridge start.launch mode:=nav map_name:=你的地图
```

### 参数

| 参数 | 默认 | 含义 |
|---|---|---|
| `mode` | `nav` | `nav` 导航 / `map` 建图 / `teleop` 纯手动 |
| `map_name` | 空 | **nav 模式必填**：`maps/` 下的地图文件夹名 |
| `map_file` | 空 | 地图 yaml 绝对路径（填了优先于 `map_name`） |
| `ep_sn` | 空 | EP 序列号；空则用 `rm_ep_params.yaml` 里的默认 SN |
| `ep_conn_type` | `rndis` | `rndis`(USB) / `ap`(WiFi 直连) / `sta`(路由器) |
| `ep_ip` | 空 | EP IP（空则用 SN 自动发现） |
| `use_hi12` | `true` | 是否用 HI12 外置 IMU |
| `rviz` | `false` | 要不要顺便起 RViz |

> 💡 **多数情况只需 `mode` + `map_name`**：USB 是默认接法、你自己的车 SN 已在配置文件里。
> 例如 USB 连你的车、地图叫 `教室`：
> ```bash
> roslaunch mrrep_bridge start.launch mode:=nav map_name:=教室
> ```
> 查地图名：`ls ~/EP_navigation_Ros1/src/rm_ep_navigation/maps/`

---

## 2. 三模式详解

### 🧭 nav — 导航（自主 + 手动可随时接管）

- **起的栈**：`navigation.launch`(move_base + AMCL + map_server + EKF) + `hrp_follower_node` + twist_mux + rosbridge
- **WebRop 操作**：
  - HRP Path 模式画曲线 / Navigate 模式点目标 → 小车自主走
  - **按 WebRop 键盘 → 立即手动接管**；松手 0.5s → 自动回自主
- ⚠️ **先给 AMCL 初始位姿**：RViz "2D Pose Estimate" 或 WebRop Relocate 模式点一下车的真实位置，否则定位不准、move_base 规划会乱
- **命令**：`roslaunch mrrep_bridge start.launch mode:=nav map_name:=你的地图`

### 🗺️ map — 建图（gmapping）

- **起的栈**：`mapping.launch`(gmapping + EKF) + `slam_bridge` + twist_mux + rosbridge（**无 move_base**）
- **WebRop 操作**：WASD 开车走一圈，看地图实时长出；点 WebRop 的 **SlamPanel `stop` / `save`** → `slam_bridge` 调 `save_map.sh` 把图存下来
- **存图位置**：`maps/<时间戳>/`（或用 `save:名字` 指定名字）
- **命令**：`roslaunch mrrep_bridge start.launch mode:=map`
- 建完 Ctrl+C，切回 `mode:=nav map_name:=新地图名` 用新图

### 🎮 teleop — 纯手动

- **起的栈**：底盘 + 雷达 + EKF + twist_mux + rosbridge（**无导航无建图**）
- **WebRop 操作**：WASD 遥控 + 看激光点
- **命令**：`roslaunch mrrep_bridge start.launch mode:=teleop`

---

## 3. `/cmd_vel` 与 twist_mux（核心机制）

**解决"导航时键盘不能控制"的关键**：

```
WebRop 键盘 ──▶ /teleop_vel ──┐
                              ├─▶ twist_mux ──▶ /cmd_vel ──▶ EP 底盘
move_base  ──▶ /cmd_vel_raw ──┘   (手动优先级 10, 自动优先级 1)
```

- **twist_mux 是 `/cmd_vel` 的唯一写者**（底盘订阅 `/cmd_vel`）。move_base 不再直接发 `/cmd_vel`，改发 `/cmd_vel_raw`；WebRop 键盘发 `/teleop_vel`。
- 手动优先级 10 > 自动 1：**按键盘立即接管**，停止发送 0.5s 后回自主。
- **所有模式 twist_mux 都常驻**：map/teleop 模式没有 move_base，`/cmd_vel_raw` 空，twist_mux 直通 `/teleop_vel`，键盘照常管用——所以不用为每个模式单独配。
- 这要求小车仓库 `navigation.launch` 把 move_base 的输出重映射到 `cmd_vel_raw`（`start.launch` 已自动传 `cmd_vel_topic:=cmd_vel_raw`；**向后兼容**，单独跑 `navigation.launch` 仍发 `/cmd_vel`，不受影响）。

---

## 4. 日常流程（每次重启机器人 PC 后）

```bash
# 1. 确认 USB 线插好、EP 开机、HI12 接好
# 2. source（或写进 ~/.bashrc 一劳永逸）
source ~/mrrep_ws/devel/setup.bash
# 3. 一键启动（按需选模式）
roslaunch mrrep_bridge start.launch mode:=nav map_name:=你的地图
```
开发 PC：WebRop `npm run dev` → 浏览器连 `ws://机器人IP:9090` → 操作。

---

## 5. WebRop 端操作

1. **连接**：关掉 Mock，rosbridge 地址填 `ws://机器人IP:9090`，点连接。
2. **nav**：HRP Path 模式画曲线 → 发送；或 Navigate 模式点目标；按 **WASD 手动接管**。
3. **map**：WASD 开车走一圈；SlamPanel 点 `stop`/`save` 存图。
4. **teleop**：WASD 遥控。
5. 看到地图 + 小车 + 激光 = 通信正常。

> WebRop 必须用 **devel 分支**（`/cmd_vel`→`/teleop_vel` 的改动在 devel）。

---

## 6. 排错

| 现象 | 排查 |
|---|---|
| EP 连不上 / 底盘不动 | USB 线、EP 开机；`rostopic echo /odom` 有没有；`rm_ep_params.yaml` 的 SN 对不对；必要时 `ep_sn:=你的SN` |
| WebRop 连不上 rosbridge | `ss -tlnp \| grep 9090` 必须是 `0.0.0.0:9090`；防火墙放行 9090；地址对不对 |
| WebRop 连上但没地图/车 | `rosnode list` 看 map_server/amcl 在不在；`/map` `/odom` 有没有数据 |
| 导航时键盘不接管 | `rostopic echo /teleop_vel`（按键盘时应有）→ `/cmd_vel`（twist_mux 输出）；twist_mux 在不在跑；WebRop 是不是 devel 分支 |
| 画路径小车不走 | 看 `hrp_follower_node` 终端日志；`/move_base/status`；AMCL 定位准不准；目标点是否在障碍物上 |
| 建图存图没反应 | `slam_bridge` 终端日志；gmapping 在跑吗；WebRop 发的 `/webrop/slam_command` 收到没 |
| `Cannot locate package mrrep_bridge` | `source ~/mrrep_ws/devel/setup.bash`；`rospack find mrrep_bridge` |
| twist_mux 相关报错 | `sudo apt install ros-noetic-twist-mux` 装了没 |
| 车头方向不对（WebRop 里） | WebRop 的 `RobotModel.tsx` 是否 devel 分支（`rotation.y = -yaw` 修正） |

---

## 7. 速查

**话题契约**
| 话题 | 类型 | 谁发 → 谁收 |
|---|---|---|
| `/hrp_path` | nav_msgs/Path (frame=map) | WebRop / HL2 → `hrp_follower_node` |
| `/teleop_vel` | geometry_msgs/Twist | WebRop 键盘 → twist_mux |
| `/cmd_vel_raw` | geometry_msgs/Twist | move_base → twist_mux |
| `/cmd_vel` | geometry_msgs/Twist | twist_mux → EP 底盘 |
| `/move_base_simple/goal` | geometry_msgs/PoseStamped | hrp_follower → move_base |
| `/map` `/odom` `/scan` | — | 小车栈 → WebRop 显示 |
| `/webrop/slam_command` | std_msgs/String | WebRop → slam_bridge |

**本仓库文件**
- `mrrep_bridge/launch/start.launch` — ⭐ 一键启动
- `mrrep_bridge/config/twist_mux.yaml` — 速度仲裁配置
- `mrrep_bridge/scripts/hrp_follower_node.py` — 路径跟随
- `mrrep_bridge/scripts/slam_bridge.py` — 建图存图桥接

**相关文档**：[architecture.md](architecture.md) · [setup-guide.md](setup-guide.md) · `plan/` 复现计划书
