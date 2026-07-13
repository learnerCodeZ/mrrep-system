# 架构与话题契约

## 三个组件仓库怎么连

```
┌─────────── 你的电脑 ───────────┐    ┌────────── HoloLens2 ──────────┐
│ WebRop 浏览器（鼠标画图，2D 基线） │    │ Unity MR App（手势地面画图）    │
│ roslibjs                        │    │ ROS-TCP-Connector + MRTK      │
└──────────┬──────────────────────┘    └──────────────┬────────────────┘
           │ ws://机器人IP:9090                        │ tcp://机器人IP:10000
           │ 方案 C · JSON/WebSocket                   │ 方案 B · 二进制 TCP
           ▼                                          ▼
┌──────────────────── 机器人 PC（ROS1 Noetic）────────────────────┐
│  rosbridge_server (:9090)       ← 并行，互不冲突 →     ros_tcp_endpoint (:10000) │
│                                     │                                    │
│                                     ▼                                    │
│                    /hrp_path  (nav_msgs/Path, frame=map)                │
│                    ← 两个客户端发同一个话题，机器人侧不关心来源 →          │
│                                     │                                    │
│                                     ▼                                    │
│                       hrp_follower_node.py   [本仓库 mrrep_bridge]      │
│                                     │                                    │
│                                     ▼                                    │
│                       /move_base_simple/goal → move_base → /cmd_vel      │
│                                     │                                    │
│                                     ▼                                    │
│                                rm_ep_driver → EP 底盘                    │
│                                                                          │
│  /map ◀ map_server   /odom ◀ EKF(融合HI12)   /scan ◀ rplidar            │
└──────────────────────────────────────────────────────────────────────────┘
```

## 话题契约（系统枢纽）

| 话题 | 消息类型 | frame | 谁发 | 谁收 |
|---|---|---|---|---|
| **`/hrp_path`** | `nav_msgs/Path` | `map` | WebRop（rosbridge）/ HoloLens2（ROS-TCP） | `hrp_follower_node` |
| `/move_base_simple/goal` | `geometry_msgs/PoseStamped` | `map` | `hrp_follower_node` | move_base |
| `/cmd_vel` | `geometry_msgs/Twist` | — | move_base / 遥控 | rm_ep_driver |
| `/map` | `nav_msgs/OccupancyGrid` | — | map_server | WebRop（显示） |
| `/odom` | `nav_msgs/Odometry` | — | EKF | WebRop（显示机器人） |

**核心设计**：`/hrp_path` 是统一接口。客户端（Web 或 HL2）只管画好路径发这条话题；机器人侧 `hrp_follower_node` 逐点喂 move_base。所以客户端可替换、可并行，机器人侧代码不变。

## 两种客户端对比

| | WebRop（方案 C） | HoloLens2（方案 B） |
|---|---|---|
| 传输 | rosbridge :9090（JSON/WebSocket） | ROS-TCP-Endpoint :10000（二进制 TCP） |
| 角色 | 论文 2D 基线 + 监控大屏 | 论文 MR 实验（真复现） |
| 画图方式 | 鼠标在浏览器地图上画 | 手势在真实地面上画 |
| 部署难度 | `npm run dev` 即可 | 需 Unity 构建 UWP/ARM64 部署到头显 |

两者可**同时连**同一个 ROS graph，正好对应论文用户实验的两种对照条件。

## MRRP-Navigation（HL2 仓库）接入说明（已核实）

同作者 learnerCodeZ 的 [MRRP-Navigation](https://github.com/learnerCodeZ/MRRP-Navigation) 是个**基本完整**的 Unity HL2 客户端 + 自带虚拟车 ROS 包。核实结论：

- ✅ **ROS1 Noetic** + **ROS-TCP-Connector** —— 和本系统一致，**不用转 ROS2**。
- ✅ 话题名就是 `/hrp_path`，走 ROS-TCP 发。
- ⚠️ **但它发的是 `geometry_msgs/PoseArray`，而 WebRop 和本仓库 `hrp_follower_node` 用的是 `nav_msgs/Path`** —— 类型不一致。Part II 接入时三选一：
  1. 改 MRRP-Navigation 的 `Assets/Scripts/ROS/PathSender.cs` 改发 `nav_msgs/Path`（**推荐**，统一到 WebRop 契约）；
  2. 让 `hrp_follower_node` 同时订阅 `PoseArray`；
  3. 加个 `PoseArray → Path` 中转节点。
- ⚠️ 它当前是**全虚拟仿真**（Unity 里一辆虚拟小车跑 `pure_pursuit.py`，**不接真 EP**）。接入本系统 = 把它的 `/hrp_path` 指向 EP_navigation_Ros1 的 ROS master，绕过它自带的虚拟车节点。
- ⚠️ Unity 锁 `2022.3.62f1c1`（**末尾 c1 = 中国版**，普通 Hub 可能没这个 build）；MRTK 是 **2.8.3 不是 3**；**无 LICENSE**（默认全保留版权，二次分发需作者授权）。

## 扩展：WebRop 显示 HL2 位置

HoloLens2 额外发 `/hololens/pose`（`geometry_msgs/PoseStamped`，frame=`map`，~10Hz），WebRop 加一个 rosbridge 订阅 + 标记即可同屏显示车和头显位置。详见复现计划书的"扩展功能"章节。
