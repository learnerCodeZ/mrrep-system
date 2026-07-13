# MRReP 复现计划书 — HoloLens2 + EP 小车（完整版）

> **最终目标**：用 **HoloLens2（混合现实）** 作为手绘路径客户端，接入 DJI RoboMaster EP 导航小车（ROS1），复现 MRReP 论文（arXiv:2604.00059）——**戴着头显在真实地面上手绘一条路径 → 小车按所画形状跟随导航**。
>
> **两阶段战略**：
> - **Part I（第一阶段）：WebRop + rosbridge 快速验证**。先不碰 HoloLens2 工具链，用电脑浏览器版 WebRop 把"机器人侧建图 / 导航 / 路径跟随"整条链路跑通、调好。好处：快、好调试、WebRop 自带 Mock 模式。
> - **Part II（第二阶段）：接入 HoloLens2**。机器人侧的路径跟随节点 `hrp_follower_node` 与第一阶段**完全共用、零改动**——HoloLens2 端只要发同样的话题 `/hrp_path`。这一阶段全是 Unity / HL2 客户端工作。
>
> **核心设计**：机器人侧只认 `/hrp_path` 这一个话题，不管是谁发的（WebRop 浏览器 or HoloLens2）。所以 Part I 调好的机器人侧，Part II 直接复用。

---

## 0. 一句话方案

```
[客户端]  ──发 /hrp_path──▶  [机器人PC]  ──▶  hrp_follower_node  ──▶  move_base  ──▶  EP 底盘

Part I 客户端 = WebRop 浏览器   (经 rosbridge,  ws://IP:9090)
Part II 客户端 = HoloLens2 Unity (经 ROS-TCP,   tcp://IP:10000)
两者可以同时连，机器人侧完全一样。
```

> HoloLens2 端画完路径按 SEND → 发 `nav_msgs/Path` 到 `/hrp_path` → 机器人侧自己写的 **`hrp_follower_node.py`** 把这条路径逐点喂给 `move_base` → EP 小车按形状跟随。
>
> ⚠️ **核心认知**：WebRop / HoloLens2 **只负责画图和发 `/hrp_path`**。WebRop 仓库里自带的 `hrp_planner_node.py` 是**空壳**（只转发不规划），所以"让机器人真正跟形状"这一层**必须我们自己写**。这是整个计划里唯一需要自己开发的 ROS 节点（Part I 的 Phase 4），写完后 Part II 直接复用。

---

## 1. 系统架构（最终：双客户端并行）

```
┌──────────────── 你的电脑 ────────────────┐    ┌─────────── HoloLens2 ───────────┐
│  WebRop 浏览器（鼠标画图，2D 基线）         │    │  Unity MR App（手势在地面画图）   │
│  roslibjs                                 │    │  ROS-TCP-Connector + MRTK3       │
└──────────────┬────────────────────────────┘    └──────────────┬───────────────────┘
               │ ws://机器人IP:9090                              │ tcp://机器人IP:10000
               │ （方案 C · JSON/WebSocket）                     │ （方案 B · 二进制 TCP）
               ▼                                                 ▼
┌──────────────────────────────── 机器人 PC（ROS1 Noetic）────────────────────────────┐
│  rosbridge_server (:9090)         ← 并行，互不冲突 →         ros_tcp_endpoint (:10000) │
│                                            │                                          │
│                                            ▼                                          │
│                          /hrp_path  (nav_msgs/Path, frame=map)                          │
│                          ← 两个客户端发同一个话题，机器人侧不关心来源 →                  │
│                                            │                                          │
│                                            ▼                                          │
│                        hrp_follower_node.py  【Part I 写一次，Part II 零改动复用】       │
│                                            │                                          │
│                                            ▼                                          │
│                          /move_base_simple/goal  →  move_base  →  /cmd_vel              │
│                          (global: NavfnROS · local: teb_local_planner 全向)              │
│                                            │                                          │
│                                            ▼                                          │
│                                       rm_ep_driver → EP 底盘                            │
│                                                                                         │
│   /map ◀── map_server    /odom ◀── EKF(融合HI12)    /scan ◀── rplidar    /tf ◀── AMCL   │
└─────────────────────────────────────────────────────────────────────────────────────────┘
```

**Part I 只用左半边**（WebRop + rosbridge）；**Part II 加上右半边**（HoloLens2 + ROS-TCP-Endpoint）。两者最终可以**同时**连，正好是论文用户实验的两种对照条件。

---

## 2. 组件清单与角色

| 组件 | 位置 | 角色 | 现状 | 哪一阶段 |
|---|---|---|---|---|
| **WebRop** | 你的电脑（浏览器） | 手绘路径客户端 + 监控屏 | ✅ 开箱即用，含 Mock 模式 | Part I |
| **HoloLens2 + Unity App** | 头显 | MR 手绘路径客户端（最终目标） | ❌ 需自己开发 | Part II |
| **rosbridge_server** | 机器人 PC | WebSocket↔ROS 翻译（给 WebRop） | ✅ apt 装即可 | Part I |
| **ROS-TCP-Endpoint** | 机器人 PC | 二进制 TCP↔ROS（给 HoloLens2） | ✅ clone 即可 | Part II |
| **EP_navigation_Ros1** | 机器人 PC | 底盘驱动+SLAM+AMCL+move_base | ✅ 开箱即用，**地图为空**需先建 | 两阶段共用 |
| **hrp_follower_node.py** | 机器人 PC | 把 `/hrp_path` 转成 move_base 目标序列 | ❌ **需自己写**（核心开发件） | Part I 写，Part II 复用 |
| （可选）自定义全局规划器插件 | 机器人 PC | 让 move_base 直接吃手绘折线（高保真平滑） | ❌ 需自己写 | Phase 5 |

---

## 3. 话题契约与设计原则

### 🎯 统一接口：`/hrp_path`

无论 WebRop 还是 HoloLens2，客户端画完路径都发同一条消息：

| 话题 | 消息类型 | 含义 |
|---|---|---|
| **`/hrp_path`** | `nav_msgs/Path`（`frame_id=map`） | 手绘参考路径折线（一串 PoseStamped） |

机器人侧 `hrp_follower_node` 只订阅它。**这就是两阶段能零改动复用的根本原因。**

### WebRop 发布的其他话题（Part I 对接用）
| 话题 | 消息类型 | 含义 | 谁消费 |
|---|---|---|---|
| `/hrp_speeds` | `std_msgs/String`（JSON） | 每段速度（0.05~2.0 m/s，13 档） | （进阶）速度调节 |
| `/move_base_simple/goal` | `geometry_msgs/PoseStamped` | 单点导航终点 | move_base 原生 ✅ |
| `/waypoint_goals` | `std_msgs/String`（JSON 数组） | Navigate 模式多航点 | （可选）航点序列器 |
| `/cmd_vel` | `geometry_msgs/Twist` | 手动遥控（WASD） | 底盘驱动 ✅ |
| `/hrz_zones` | `std_msgs/String`（JSON） | HRZ 禁区多边形 | （进阶）costmap 注入 |
| `/initialpose` | `geometry_msgs/PoseWithCovarianceStamped` | AMCL 初始定位 | AMCL ✅ |

### WebRop 订阅的话题（机器人侧要提供的）
| 话题 | 消息类型 | 注意 |
|---|---|---|
| `/map` | `nav_msgs/OccupancyGrid` | 必须，否则 3D 地图为空 |
| `/odom` | `nav_msgs/Odometry` | 机器人位姿 |
| `/move_base/NavfnROS/plan` | `nav_msgs/Path` | ⚠️ 命名空间硬编码 NavfnROS，见坑#4 |
| `/scan`、`/particlecloud`、`/move_base/status` 等 | 标准类型 | 监控用，可选 |

### WebRop 启动配置
- 开发服务器：`http://localhost:3000`（`npm run dev`）
- rosbridge 地址：默认 `ws://localhost:9090`，**UI 里有输入框可改**（`rosStore.setUrl`），改成 `ws://机器人IP:9090`
- **Mock 开关**：UI 可切 Mock 模式，完全脱离 ROS 在浏览器里模拟（含 A* 寻路、机器人运动、HRP 跟随）——**开发期神技**

---

# Part I — 第一阶段：WebRop 快速验证（Phase 0–6）

> **目标**：先不碰 HoloLens2 工具链，用 WebRop 把"机器人侧建图 / 导航 / 路径跟随"整条链路跑通、调好。每个阶段都有**出口标准**和**预计耗时**，前一阶段没通就不要进下一阶段。
>
> **这一阶段结束，你就有一个能用的"Web 画路径 → 小车跟随"系统，且机器人侧代码在 Part II 零改动复用。**

### Phase 0 — 环境准备（0.5 天）

**机器人 PC（Ubuntu 20.04 + ROS Noetic）：**
```bash
# 1. ROS Noetic（假设已装；若没有按 wiki 装）
# 2. 小车仓库
cd ~/catkin_ws/src
git clone https://github.com/learnerCodeZ/EP_navigation_Ros1.git
# 3. rosbridge
sudo apt update && sudo apt install -y ros-noetic-rosbridge-suite
# 4. 编译（首次慢：rplidar_ros 自带 C++ SDK 要编译）
cd ~/catkin_ws && catkin_make
source devel/setup.bash
```

**你的电脑（Windows/Mac）：**
```bash
# Node.js 18+（去 nodejs.org 装）
git clone https://github.com/Harriet9410/WebRop.git
cd WebRop
npm install      # 装依赖
```

**网络准备：**
- 机器人 PC 和你的电脑在**同一局域网**（同一路由器/WiFi）。
- 查机器人 PC 的 IP：`ip addr` 或 `hostname -I`，记下来（假设 `192.168.1.50`）。
- 机器人 PC 防火墙放行 9090 端口：`sudo ufw allow 9090`（或 `sudo ufw disable` 测试用）。

**✅ 出口标准**：`roscore` 能起；`npm -v` 有输出；两边能互相 `ping` 通。

---

### Phase 1 — WebRop 离线 Mock 模式跑通（0.5 天，**不依赖机器人**）

目的：先在浏览器里熟悉 WebRop，验证 HRP 画路径、导航、监控 UI 都正常，不用管机器人。

```bash
cd WebRop
npm run dev      # 开 http://localhost:3000
```

浏览器打开后：
1. 找到 **Mock 模式开关，打开**。
2. 试着画 HRP 路径（HRP Path 模式，鼠标拖拽）、画 HRZ 禁区、点击导航（Navigate 模式）。
3. 观察 3D 场景里模拟机器人是否按路径走、A* 是否避障。

**✅ 出口标准**：Mock 模式下能画路径、模拟机器人能跟随、UI 各功能点得动。**这步通了说明 WebRop 本身没问题。**

> 💡 这阶段还能截图、录屏，提前准备论文/汇报演示素材。

---

### Phase 2 — 机器人侧：建图 + 导航基线（1~2 天）

目的：让小车仓库本身的"RViz 点 2D Nav Goal → 小车开过去"跑通。**这是后续一切的基础**，且 `maps/` 出厂是空的，**必须先建图**。

**2.1 启动底盘 + 激光 + IMU，遥控建图**
```bash
# 终端1：建图（gmapping）
roslaunch rm_ep_navigation mapping.launch use_hi12:=true

# 终端2：键盘遥控，推着小车把环境走一遍
rosrun rm_ep_driver ep_teleop_keyboard.py

# 走完一圈回到起点后，终端3：存图
rosrun rm_ep_navigation save_map.sh mymap
# 生成 maps/mymap.yaml 和 maps/mymap.pgm
```

> ⚠️ `use_hi12:=true`（外置 HI12 九轴 IMU）是**默认且承重**的——给磁力计稳定航向。没 HI12 的话麦轮打滑、AMCL 严重漂，退而求其次用 `use_hi12:=false enable_imu:=true`。

**2.2 跑导航**
```bash
# 终端1：导航 bringup（move_base + AMCL + EKF + map_server）
roslaunch rm_ep_navigation navigation.launch map_name:=mymap use_hi12:=true

# 终端2：RViz
rviz    # 加载仓库自带的 nav.rviz 配置
```
在 RViz 里：
1. "2D Pose Estimate" 点小车真实位置（给 AMCL 初值）。
2. "2D Nav Goal" 点一个目标 → 小车开过去。

**✅ 出口标准**：RViz 点目标，小车可靠地开过去、避障。**move_base/AMCL/TEB 全栈 OK。**

> ⚠️ EP SDK 内部把 y/yaw 取反（匹配 RoboMaster SDK）。驱动自己处理了，**外部只要发标准 REP-103**。除非绕过 move_base 直接发 `/cmd_vel`，否则不用管。

---

### Phase 3 — 起 rosbridge，WebRop 连上机器人（0.5 天）

目的：让 WebRop 浏览器看到机器人的 `/map`、`/odom`，能在 3D 场景里显示真实地图和机器人位姿。**此时还不能跟路径**，只验证通信。

**机器人 PC：**
```bash
# navigation.launch 还开着的前提下
roslaunch rosbridge_server rosbridge_websocket.launch port:=9090
# 确认监听 0.0.0.0：另开终端 ss -tlnp | grep 9090 应显示 0.0.0.0:9090 或 *:9090
```

**你的电脑浏览器：**
1. WebRop 里把 **Mock 关掉**。
2. rosbridge 地址改成 `ws://192.168.1.50:9090`（你的机器人 IP）。
3. 点连接。

**✅ 出口标准**：
- WebRop 显示 connected。
- 3D 场景出现你建的栅格地图（`/map`）。
- 机器人模型在正确位置、随小车移动（`/odom`）。
- Navigate 模式点单目标 → 小车开过去（走 `/move_base_simple/goal`，move_base 原生支持）。

---

### Phase 4 — 【核心开发】路径注入层：hrp_follower_node（1~2 天）

目的：写一个 ROS 节点，订阅 `/hrp_path`，把折线**逐点**喂给 move_base，让小车按画的形状走。**这是 MRReP 功能的真正实现，也是 Part II 要复用的核心件。**

#### 4.1 新建 catkin 包
```bash
cd ~/catkin_ws/src
catkin_create_pkg mrrep_bridge rospy geometry_msgs nav_msgs move_base_msgs actionlib
cd mrrep_bridge && mkdir scripts launch
```

#### 4.2 写 `scripts/hrp_follower_node.py`
> 设计：用 actionlib 连 move_base 的 action server（比单纯发 `/move_base_simple/goal` 稳，能拿成功/失败/取消）。收到 `/hrp_path` 后逐点发送，成功一个发下一个。

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
hrp_follower_node.py
订阅 /hrp_path (nav_msgs/Path)，逐点喂给 move_base，让机器人按手绘折线跟随导航。
Part I（WebRop）和 Part II（HoloLens2）共用此节点——它只认 /hrp_path，不关心发送方。
"""
import rospy
import actionlib
from nav_msgs.msg import Path
from move_base_msgs.msg import MoveBaseAction, MoveBaseGoal
from actionlib_msgs.msg import GoalStatus

class HrpFollower:
    def __init__(self):
        self.path, self.idx, self.busy, self.frame = [], 0, False, "map"
        self.client = actionlib.SimpleActionClient("move_base", MoveBaseAction)
        rospy.loginfo("等待 move_base action server...")
        self.client.wait_for_server()
        rospy.loginfo("move_base 已连上。")
        rospy.Subscriber("/hrp_path", Path, self.cb_path, queue_size=1)
        rospy.loginfo("已订阅 /hrp_path。画路径并发送即可（WebRop 或 HoloLens2 均可）。")

    def cb_path(self, msg):
        poses = list(msg.poses)
        if len(poses) < 2:
            rospy.logwarn("路径点数 < 2，忽略。"); return
        self.frame = msg.header.frame_id or "map"
        # 收到新路径：若有正在执行的目标，先取消
        if self.busy:
            self.client.cancel_goal()
        self.path, self.idx = poses, 0
        rospy.loginfo("收到新路径，共 %d 个航点，frame=%s", len(poses), self.frame)
        self.send_next()

    def send_next(self):
        if self.idx >= len(self.path):
            rospy.loginfo("✅ 路径全部执行完成。"); self.busy = False; return
        self.busy = True
        goal = MoveBaseGoal()
        goal.target_pose = self.path[self.idx]
        goal.target_pose.header.frame_id = self.frame
        goal.target_pose.header.stamp = rospy.Time.now()
        rospy.loginfo("→ 前往航点 %d/%d", self.idx + 1, len(self.path))
        self.client.send_goal(goal, done_cb=self.cb_done)

    def cb_done(self, status, result):
        if status == GoalStatus.SUCCEEDED:
            rospy.loginfo("  航点 %d 到达。", self.idx + 1); self.idx += 1; self.send_next()
        elif status in (GoalStatus.ABORTED, GoalStatus.REJECTED):
            rospy.logwarn("  航点 %d 失败(status=%d)，跳过。", self.idx + 1, status)
            self.idx += 1; self.send_next()
        elif status == GoalStatus.PREEMPTED:
            rospy.loginfo("  航点 %d 被取消（收到新路径）。", self.idx + 1); self.busy = False
        else:
            rospy.logwarn("  航点 %d 状态=%d", self.idx + 1, status); self.idx += 1; self.send_next()

if __name__ == "__main__":
    rospy.init_node("hrp_follower_node")
    HrpFollower()
    rospy.spin()
```

```bash
chmod +x scripts/hrp_follower_node.py
cd ~/catkin_ws && catkin_make && source devel/setup.bash
```

#### 4.3 联调测试
```bash
# 机器人 PC 三个终端
roslaunch rm_ep_navigation navigation.launch map_name:=mymap use_hi12:=true   # 1 导航
roslaunch rosbridge_server rosbridge_websocket.launch port:=9090              # 2 rosbridge
rosrun mrrep_bridge hrp_follower_node.py                                      # 3 我们的节点
```
浏览器 WebRop 连上 → HRP Path 画一条曲线 → 发送 → **小车沿画的线一段段走**。

**无头验证**（不开 WebRop，命令行发假路径测节点）：
```bash
rostopic pub /hrp_path nav_msgs/Path "{header: {frame_id: 'map'}, poses: [
  {header: {frame_id: 'map'}, pose: {position: {x: 1.0, y: 0.0, z: 0.0}, orientation: {w: 1.0}}},
  {header: {frame_id: 'map'}, pose: {position: {x: 1.0, y: 1.0, z: 0.0}, orientation: {w: 1.0}}},
  {header: {frame_id: 'map'}, pose: {position: {x: 0.0, y: 1.0, z: 0.0}, orientation: {w: 1.0}}}
]}" -1
```
小车应依次走 (1,0)→(1,1)→(0,1)。

**✅ 出口标准**：WebRop 画任意折线，小车沿折线形状走完。**Part I 核心复现完成。🎉**

> 说明：逐点喂 move_base 的方式，小车每点之间走 move_base 自己规划的局部路径（直线为主），拐点会停下再转向，**不平滑但能跑通**。要丝滑跟踪进 Phase 5。**注意：Phase 4 这个节点在 Part II 完全复用，HoloLens2 发的 `/hrp_path` 它照样吃。**

---

### Phase 5 — （进阶）让小车丝滑跟曲线（1~2 天，可选）

**选择 A：自定义全局规划器插件 + TEB via-point（推荐）**
小车仓库 `teb_local_planner_params.yaml` **已配 via-point**（`weight_viapoint:1.0`、`global_plan_viapoint_sep:0.5`、`holonomic_robot:true`）。写一个 `nav_core::BaseGlobalPlanner` 插件，`makePlan()` 直接返回 `/hrp_path` 原样折线，TEB 就会把它当全局路径并尊重 via-point，平滑跟踪形状。

**选择 B：独立 pure-pursuit 节点（最还原论文，但丢避障）**
rospy 节点吃 `/hrp_path`，纯追踪算法算速度直接发 `/cmd_vel`，绕过 move_base。最贴近论文的 Pure Pursuit 控制器，但失去 move_base 避障。记得发标准 REP-103 Twist（驱动会自己翻 y/yaw）。

> 推荐：**先 Phase 4 跑通，再按选择 A 提升平滑度**。

---

### Phase 6 — （进阶）HRZ 禁区 + 分段速度（1 天，可选）

- **HRZ→costmap**：写节点把 `/hrz_zones` 禁区多边形写进 move_base costmap。WebRop 自带的 `hrz_costmap_node.py` 是空壳，要自己实现。
- **分段速度**：让 `hrp_follower_node` 读 `/hrp_speeds`，进入对应段时调 TEB 的 `max_vel_x`。

---

### Part I 一键启动

`mrrep_bridge/launch/mrrep_web.launch`：
```xml
<launch>
  <include file="$(find rm_ep_navigation)/launch/navigation.launch">
    <arg name="map_name" value="mymap"/>
    <arg name="use_hi12" value="true"/>
  </include>
  <include file="$(find rosbridge_server)/launch/rosbridge_websocket.launch">
    <arg name="port" value="9090"/>
  </include>
  <node name="hrp_follower_node" pkg="mrrep_bridge" type="hrp_follower_node.py" output="screen"/>
</launch>
```
以后 `roslaunch mrrep_bridge mrrep_web.launch`，浏览器开 WebRop 连上即可。

---

# Part II — 第二阶段：接入 HoloLens2（最终目标）

> **战略**：Part I 调好的机器人侧**完全不动**——`hrp_follower_node` 继续订阅 `/hrp_path`，move_base/AMCL/EKF/地图继续跑。唯一新增：机器人侧**并行**起一个 `ros_tcp_endpoint`（端口 10000）给 HoloLens2 用，它和 rosbridge（9090）**互不冲突、可同时跑**。
>
> **HoloLens2 端的工作本质**：用 Unity 写一个 MR App，实现"手势画地面路径 → 转 map 坐标 → 发到 `/hrp_path`"——等于把 WebRop 那个鼠标画图客户端，换成戴着头显用手画。

### Phase 7 — HoloLens2 开发环境（1 天）

> **⚠️ 红线：Unity 版本**。必须 **Unity 2022.3 LTS**（如 2022.3.22f1）。Unity 在 **2025-06-23 之后**移除了 HoloLens2 支持，**Unity 6 / Unity 2023 LTS 一律不能用**。装好后**关闭 Unity Hub 自动升级**。

| 项 | 说明 |
|---|---|
| Unity Hub + Unity 2022.3 LTS | Hub > Installs > Add Modules 勾 **UWP Build Support** + **Windows Build Support (IL2CPP)**——两者必需 |
| Visual Studio 2022 | workloads：`.NET desktop`、`Desktop C++`（MSVC v143）、`Universal Windows Platform development`（勾 USB Device Connectivity + C++ UWP tools）、`Game development with Unity` |
| Windows SDK | `10.0.19041`（HL2 基线）+ 一个新的（22621/26100）备用 |
| Mixed Reality Feature Tool | 导入 MRTK3 + Microsoft OpenXR 插件 |
| Unity 包 | `com.unity.xr.openxr`(1.14.x)、`com.microsoft.mixedreality.openxr`、`com.unity.xr.arfoundation`、MRTK3、`com.unity.robotics.ros-tcp-connector` |
| HoloLens2 设备 | Settings > Update & Security > For developers：开发者模式 ON、Device Portal ON；首次 USB 部署用 PIN 配对 |

**✅ 出口标准**：Unity 能新建 OpenXR + MRTK3 项目；HoloLens 在 Device Portal 可见。

---

### Phase 8 — Unity↔ROS 桥（ROS-TCP，方案 B）（0.5 天）

**机器人侧**（和 rosbridge 并行，不冲突）：
```bash
cd ~/catkin_ws/src
git clone https://github.com/Unity-Technologies/ROS-TCP-Endpoint.git
cd ROS-TCP-Endpoint && git checkout main   # ⚠️ main=ROS1！main-ros2 是 ROS2，别选错
cd ~/catkin_ws && catkin_make && source devel/setup.bash
roslaunch ros_tcp_endpoint endpoint.launch  # 默认端口 10000
```

**Unity 侧**：
1. 装 ROS-TCP-Connector 包。
2. 菜单 `ROS Settings`（ROSTCPConnector）：`Protocol = ROS1`、`ROS IP = 机器人PC的IP`、`ROS Port = 10000`。

**验证往返**（先不上 HL2，Unity Editor 里跑）：写个测试脚本，Unity 启动时发一个 `PoseStamped` 到 `/move_base_simple/goal`，小车应动一下。

**✅ 出口标准**：Unity Editor 发 goal，小车响应。

> ⚠️ 分支陷阱：`main`=ROS1，`main-ros2`=ROS2。选错或 Unity Protocol 设错 → "socket 开着但消息不通"的静默失败。

---

### Phase 9 — HoloLens2 手绘 UI（MRTK3）（2~3 天）

客户端核心工作，三部分：

**9.1 地面光标**
- 从 MRTK3 `HandsAggregator` 读**食指尖/掌心**位姿。
- 从该位姿**向下 `Physics.Raycast`**，打 MRTK 空间感知系统（Spatial Awareness）生成的环境网格 → 命中点 = 地面光标全局坐标，把 hologram 锚到该点。
- 需要 `SpatialPerception` capability + 开启 MRTK 空间感知系统。

**9.2 手势画路径**
- 读 `HandsAggregator.TryGetPinchProgress`（连续捏合量）。
- 捏合越过"保持"阈值 → 开始新路径。
- 每帧当地面光标移动 > **D_th = 0.2 m**（论文值）→ 追加航点（降采样）。
- 松开捏合 → 闭合路径，终点放 goal pin。

**9.3 发送**
- 按 SEND 时**一次性**发布整条 `nav_msgs/Path` 到 `/hrp_path`（**和 WebRop 同名！机器人侧 `hrp_follower_node` 零改动复用**）。
- **不要逐帧流式发**，会淹没链路。
- 路径点 `frame_id = "map"`（见 Phase 10 坐标对齐）。

**Unity 发布 Path 要点**（ROS-TCP-Connector）：用 `ROSConnection.Send(...)` 发 `RosMessageTypes.Nav.Msgs.MPath`，航点先转 map 坐标（Phase 10）再填入 `MPath.poses`。

**✅ 出口标准**：Unity Editor（Holographic Remoting 或手模拟）能画路径，按 SEND 后机器人侧 `rostopic echo /hrp_path` 看到数据、小车开始跟随。**HL2 端核心逻辑已通。**

---

### Phase 10 — QR 码坐标对齐（1 天）

**问题**：Unity 世界坐标系和机器人 `map` 坐标系不同，画的航点是 Unity 坐标，必须转到 map 坐标才能发。

**做法（推荐 Microsoft OpenXR QR，不用 Vuforia）**：
- 在 ROS `map` 原点贴一张**物理 QR 码（≥ version 5，约 10 cm 见方）**。
- Unity 用 **Microsoft Mixed Reality OpenXR QR 追踪**（参考 `github.com/microsoft/MixedReality-QRCode-Sample`）——免费、原生、2025 年仍维护。
- ⚠️ **不要用 Vuforia**——它在 2025 年已废弃 HL2/UWP 支持。
- 检测到 QR 后，从其位姿（position + orientation）算出 **Unity↔map 的刚体变换**（旋转+平移）。
- 发送前把每个 Unity 航点经此变换转到 map 坐标。
- 路径相对 QR 原点存 JSON，设备重启后可恢复（论文也这么存）。

**注意**：QR 码 <5cm 或距离 >2~3m 会抖动/丢失，务必用大码。

**✅ 出口标准**：QR 贴在不同位置，画的路径在 RViz 里都能落在正确的 map 位置。

---

### Phase 11 — 上机部署 + 集成（1 天）

**构建 UWP 包**：
- Unity File > Build Settings，平台切 **Universal Windows Platform**。
- Architecture = **ARM64**，Build Type = D3D，Target SDK = `10.0.19041`，Min Platform = `10.0.10240`。
- Scripting Backend = **IL2CPP**，API Compatibility = **.NET Standard 2.1**。
- Player > Publishing Settings > **Capabilities 必勾**：
  - `InternetClient`、`InternetClientServer`、`PrivateNetworkClientServer`（连机器人）
  - `Webcam`（QR 追踪）
  - `SpatialPerception`（地面网格 raycast）
  - **少勾任何一个，核心功能静默失效。**
- Build（不是 Build And Run）→ 生成 UWP `.sln`。

**部署到 HoloLens2**：
- VS 2022 打开 `.sln`，Solution Platform = **ARM64**，Configuration = **Release**，右键 Deploy。
- USB 首次：选 "Machine Name"/USB，"Universal Authentication"，**需 PIN 配对**（Settings > For developers > Devices）。
- 或 Wi-Fi：选 "Remote Machine"，输入设备 IP（端口 2980）。
- 或 Device Portal：`https://127.0.0.1:10080` > Views > Apps > 装 `.appxbundle`。

**集成测试**：戴 HL2 → 看到地面 → 手势画路径 → SEND → **小车沿画的线走**。调 TEB 的 `global_plan_viapoint_sep`（平滑度）和捏合灵敏度。

**✅ 出口标准（最终复现成功）**：戴头视在真实地面画路径，小车按形状跟随。🎉🎉

---

### Phase 12 — （可选）双客户端对照实验（1 天）

此时你同时拥有：
- **WebRop**（电脑鼠标画图，方案 C）= 论文 **2D 基线**
- **HoloLens2**（手势地面画，方案 B）= 论文 **MR 实验**

两者连同一台小车、发同一个 `/hrp_path`、用同一个 `hrp_follower_node`。**这正是 MRReP 论文用户实验的两种对照条件**。可按论文实验设计（路径精度/用时/SUS/NASA-TLX）跑小规模对比，验证 MR 是否更准更直觉。

---

### Part II 一键启动（机器人侧加 ROS-TCP-Endpoint）

`mrrep_bridge/launch/mrrep_full.launch`：
```xml
<launch>
  <include file="$(find rm_ep_navigation)/launch/navigation.launch">
    <arg name="map_name" value="mymap"/>
    <arg name="use_hi12" value="true"/>
  </include>
  <!-- 给 WebRop（2D 基线 / 监控） -->
  <include file="$(find rosbridge_server)/launch/rosbridge_websocket.launch">
    <arg name="port" value="9090"/>
  </include>
  <!-- 给 HoloLens2（MR 客户端） -->
  <include file="$(find ros_tcp_endpoint)/launch/endpoint.launch"/>
  <!-- 两客户端共用的路径跟随节点 -->
  <node name="hrp_follower_node" pkg="mrrep_bridge" type="hrp_follower_node.py" output="screen"/>
</launch>
```
`roslaunch mrrep_bridge mrrep_full.launch` 后，WebRop 和 HoloLens2 都能同时连。

---

## 扩展功能：在 WebRop 上同时显示小车 + HoloLens2 位置（方案 1）

> **目标**：WebRop 浏览器里，除了小车模型，再实时显示一个 HoloLens2（佩戴者头部）位置的标记，一眼看到"车在哪、人戴的头显在哪"。
>
> **方案**：HL2 把自己头部位姿（经 QR 对齐转 map 坐标）发到 `/hololens/pose`；WebRop 加一个 rosbridge 订阅 + 一个小图标。**ROS 侧零改动**——HL2 走 ROS-TCP、WebRop 走 rosbridge，同一个 ROS graph，话题互通。

### 数据通路

```
HoloLens2 Unity（头部位姿 → QR 变换 → map 坐标）
   ──ROS-TCP(:10000)──▶  /hololens/pose (PoseStamped, frame=map, ~10Hz)
                                 │ （同一 ROS graph）
                  rosbridge(:9090) 转成 WebSocket
                                 ▼
                  WebRop 新增订阅 → 新 hololensStore → Scene3D 渲染 HL2 图标
```

### 一、HoloLens2 端：发布头部位姿（Phase 9–10 之上加一个小脚本）

HL2 的 Unity App 已有 QR 对齐（Phase 10），拿到 Unity↔map 变换。在此基础上加一个发布器，把主相机（= 头部位姿）每秒发 ~10 次：

```csharp
// HololensPosePublisher.cs —— 挂到一个 GameObject 上
using UnityEngine;
using Unity.Robotics.ROSTCPConnector;
using RosMessageTypes.Geometry;   // PoseStampedMsg, PoseMsg, PointMsg, QuaternionMsg

public class HololensPosePublisher : MonoBehaviour
{
    ROSConnection ros;
    public string topicName = "/hololens/pose";
    public float publishHz = 10f;
    public Transform mapOriginAnchor;   // QR 检测得到的 anchor：其位姿 = map 原点在 Unity 中的位姿
    float timer;

    void Start()
    {
        ros = ROSConnection.GetOrCreateInstance();
        ros.RegisterPublisher<PoseStampedMsg>(topicName);
    }

    void Update()
    {
        timer += Time.deltaTime;
        if (timer < 1f / publishHz) return;
        timer = 0f;

        // 头部在 Unity 世界坐标的位姿（HL2 上 Camera.main 就是佩戴者头部）
        Vector3 headWorld = Camera.main.transform.position;
        Quaternion headRot = Camera.main.transform.rotation;

        // 转到 map 帧（相对 QR 原点）
        Vector3 local = mapOriginAnchor.InverseTransformPoint(headWorld);
        Quaternion localRot = Quaternion.Inverse(mapOriginAnchor.rotation) * headRot;

        // ⚠️ 轴映射：Unity(左手,Y上) → ROS map(右手,Z上)，见下方坑#21，需实测校准
        var msg = new PoseStampedMsg
        {
            header = new RosMessageTypes.Std.HeaderMsg { frame_id = "map" },
            pose = new PoseMsg
            {
                position = new PointMsg(local.x, local.z, 0f),
                orientation = new QuaternionMsg(localRot.x, localRot.y, localRot.z, localRot.w)
            }
        };
        ros.Send(topicName, msg);
    }
}
```

**关键点**：
- `Camera.main.transform` 就是 HoloLens2 佩戴者的头部位姿。
- `mapOriginAnchor` 来自 Phase 10 的 QR 检测结果——把检测到的 QR 位姿赋给一个空 GameObject 的 transform。
- **轴映射**：Unity 是 Y 轴朝上、左手系；ROS map 是 Z 轴朝上、右手系。上面把 Unity 的 `local.z` 当作 ROS 的 `y`。**务必 RViz/WebRop 实测校准**：移动 HL2，看标记是否同向移动；反了就把 x 取负或交换 y/z。

### 二、WebRop 端：加一个订阅 + 一个标记（改 3 个文件，已对照源码确认）

WebRop 已有完整的"订阅 ROS 话题 → 存 store → 渲染"模式（就是显示小车那套，`connection.ts` 里 `/odom` 的写法）。照抄即可。

**改动 1：`src/ros/connection.ts` —— 加 `/hololens/pose` 订阅**

顶部变量区加：
```ts
let hololensSub: Topic | null = null;
```
在 `subscribeAll()` 里（和 `odomSub` 并列）加：
```ts
hololensSub = new Topic({
  ros, name: '/hololens/pose',
  messageType: 'geometry_msgs/PoseStamped',
  throttle_rate: 100,   // ≈10Hz
});
hololensSub.subscribe((msg: any) => {
  const p = msg.pose.position;
  const q = msg.pose.orientation;
  const rosYaw = quaternionToYaw(q.x, q.y, q.z, q.w);
  const scenePos = rosToScene(p.x, p.y);               // 复用现成 ROS→场景 变换
  useHololensStore.getState().setPose({
    x: scenePos.x, z: scenePos.z,
    yaw: Math.PI / 2 - rosYaw,                          // 复用现成 yaw 变换
    connected: true,
  });
});
```
在 `disconnect()` 里加一行清理：
```ts
try { if (hololensSub) { hololensSub.unsubscribe(); hololensSub = null; } } catch {}
```
顶部 `import { useHololensStore } from '../stores/hololensStore';`

> `rosToScene`、`quaternionToYaw`、`Math.PI/2 - rosYaw` 全是 WebRop 现成的，**和小车同一套变换**——HL2 标记自动和小车在同一地图坐标里对齐。

**改动 2：新建 `src/stores/hololensStore.ts`**（照 rosStore 抄）
```ts
import { create } from 'zustand';
export interface HololensPose { x: number; z: number; yaw: number; connected: boolean; }
interface S { pose: HololensPose | null; setPose: (p: HololensPose) => void; clear: () => void; }
export const useHololensStore = create<S>((set) => ({
  pose: null,
  setPose: (pose) => set({ pose }),
  clear: () => set({ pose: null }),
}));
```

**改动 3：`src/components/scene/Scene3D.tsx` —— 加 HL2 标记组件**
```tsx
function HololensMarker() {
  const pose = useHololensStore((s) => s.pose);
  if (!pose) return null;
  return (
    <group position={[pose.x, 0.05, pose.z]} rotation={[0, pose.yaw, 0]}>
      <mesh><sphereGeometry args={[0.12, 16, 16]} />
        <meshStandardMaterial color="#00e5ff" emissive="#00e5ff" emissiveIntensity={0.6} />
      </mesh>
      <mesh position={[0, 0, 0.2]} rotation={[Math.PI / 2, 0, 0]}>
        <coneGeometry args={[0.06, 0.2, 12]} /><meshStandardMaterial color="#00e5ff" />
      </mesh>
    </group>
  );
}
```
然后在 `Scene3D` 的 return 里，和 `{robots.map(...)}` 同级加一行 `<HololensMarker />`，并 `import { useHololensStore } from '../../stores/hololensStore';`。

> 图标样式随意——想要头显外形、视野锥、轨迹尾迹都好加（WebRop 已有 `BreadcrumbTrail`、`LaserScanVisual` 可参考）。**不要把 HL2 塞进 `fleetStore.robots` 当"第二个机器人"**——那会让导航命令可能误发到 HL2（active-robot 逻辑）；用独立 store + 独立标记最安全。

### 三、验证

1. `roslaunch mrrep_bridge mrrep_full.launch`（导航 + rosbridge + ros_tcp_endpoint + hrp_follower）。
2. WebRop 连上 → 小车模型正常（原有功能不变）。
3. HL2 戴上、Unity App 运行 → WebRop 地图上出现青色 HL2 标记。
4. 转头/走动 → 标记跟着移动、朝向跟着转。
5. **坐标校准**：把 HL2 标记挪到小车正上方，看两者是否重合；偏差大就是轴映射/QR 方向问题（见坑#21）。

**✅ 出口标准**：WebRop 同屏显示小车 + HL2 两个实体，位置/朝向都正确。

---

## 需要修改 / 新建的文件清单

| 文件 | 改什么 | 阶段 |
|---|---|---|
| `EP_navigation_Ros1/maps/` | 建图后存入 `mymap.{yaml,pgm}` | Phase 2 |
| `mrrep_bridge/scripts/hrp_follower_node.py` | **新建**（见 Phase 4.2） | Phase 4 |
| `mrrep_bridge/launch/mrrep_web.launch` | **新建**（Part I 一键启动） | Phase 4 |
| `mrrep_bridge/launch/mrrep_full.launch` | **新建**（Part II，加 ros_tcp_endpoint） | Phase 8 |
| （可选）`rm_ep_navigation/config/move_base_params.yaml` | 加 `base_global_planner: navfn/NavfnROS`（解决 WebRop 规划可视化，见坑#4） | Phase 3 |
| （进阶）自定义全局规划器插件 | 新建 C++ 包，设 `base_global_planner` | Phase 5 |
| HoloLens2 Unity 项目 | **新建**（MRTK3 + ROS-TCP-Connector + QR） | Phase 7–11 |
| WebRop `src/ros/connection.ts` | 加 `/hololens/pose` 订阅（照 odom 抄） | 扩展 |
| WebRop `src/stores/hololensStore.ts` | **新建**（存 HL2 位姿） | 扩展 |
| WebRop `src/components/scene/Scene3D.tsx` | 加 `<HololensMarker>` 组件 | 扩展 |
| HL2 Unity `HololensPosePublisher.cs` | **新建**（发头部位姿到 `/hololens/pose`） | 扩展 |

---

## 已知坑（汇总）

### 机器人侧 / Part I
1. **❗ WebRop 的 `hrp_planner_node.py` / `hrz_costmap_node.py` 是空壳**——别指望，Phase 4 自己写的 `hrp_follower_node` 才真能用。
2. **❗ `maps/` 出厂为空**——不建图 `navigation.launch` 报 "Request for map failed"，必须先 Phase 2 建图。
3. **❗ HI12 IMU 承重**——务必 `use_hi12:=true`。
4. **⚠️ WebRop 订阅 `/move_base/NavfnROS/plan`（硬编码命名空间）**——小车默认全局规划器是 NavfnDijkstra，WebRop 看不到规划线。修复：`move_base_params.yaml` 设 `base_global_planner: navfn/NavfnROS`（只影响可视化）。
5. **⚠️ rosbridge 监听地址**——确认 `ss -tlnp | grep 9090` 是 `0.0.0.0:9090` 而非 `127.0.0.1`。
6. **⚠️ 防火墙**——机器人 PC 放行 9090/10000；Windows 首次连 ws/tcp 可能弹权限。
7. **⚠️ TF 树分散**——EKF 发 `odom→base_link`、AMCL 发 `map→odom`、RSP 发 `base_link→传感器`，别乱 kill。
8. **⚠️ EP SDK 坐标翻转**——只在绕过 move_base 直接发 `/cmd_vel`（Phase 5 选择 B）时要关心，发标准 REP-103。
9. **⚠️ 默认 SN 锁死** `3JKDH3B001891M`——用 `ep_sn:=` / `ep_ip:=` 覆盖。
10. **⚠️ 国内 git clone github 可能失败**——仓库自带 Clash 代理文档；或 jsDelivr CDN 兜底。
11. **⚠️ 逐点法拐点停顿**——Phase 4 通了但拐弯会停，正常；要平滑进 Phase 5。

### HoloLens2 / Part II
12. **❗ Unity 版本红线**——必须 2022.3 LTS；Unity 6/2023 不支持 HL2（2025-06-23 后移除）。
13. **❗ ROS-TCP-Endpoint 分支陷阱**——`main`=ROS1，`main-ros2`=ROS2，选错静默失败。
14. **⚠️ USB 首次部署 PIN 配对**——配对过期抛 `DEP6957` "Failed to connect to 127.0.0.1"（看着像网络错，其实是配对失效，重新配）。
15. **⚠️ Vuforia 废弃**——HL2/UWP 2025 已废弃，用 Microsoft OpenXR QR。
16. **⚠️ QR 码尺寸**——≥ version 5 / ~10cm，太小太远会抖。
17. **⚠️ Capabilities**——`SpatialPerception`（地面 raycast）+ `Webcam`（QR）+ 三个 Network 必勾。
18. **⚠️ 必须 ARM64 + Release**——Debug 在 HL2 上慢得多，会卡到捏合识别失败。
19. **⚠️ HL2 2027 进入支持末期**——整个工具链是 deprecated 目标，**快照每个依赖版本**（Unity 补丁号、OpenXR 插件、MRTK3、ROS-TCP-Connector/Endpoint）。
20. **⚠️ 不要逐帧发路径**——SEND 时整条一次发，设备上用 D_th=0.2m 降采样。

### 扩展功能（WebRop 显示 HL2 位置）
21. **⚠️ Unity↔ROS 轴映射**——HL2 头部位姿从 Unity(左手系,Y上) 转 map(右手系,Z上) 时，x/y/z 和 yaw 的对应要实测校准（RViz/WebRop 里看是否同向），错了标记会镜像或转 90°。
22. **⚠️ `/hololens/pose` 别发太快**——它走 rosbridge JSON，10Hz 够用；订阅端 `throttle_rate:100` 也限了速。
23. **⚠️ 别把 HL2 塞进 `fleetStore.robots`**——会让导航命令可能误发到 HL2（active-robot 逻辑）；用独立 `hololensStore` + 独立标记。

---

## 整体时间估算与里程碑

| 阶段 | 内容 | 预估 | 里程碑 |
|---|---|---|---|
| **Part I — WebRop 快速验证** | | | |
| Phase 0 | 环境 | 0.5 天 | 能编译、能 npm run |
| Phase 1 | WebRop Mock | 0.5 天 | 浏览器模拟跑通 🎯 |
| Phase 2 | 建图+导航基线 | 1~2 天 | RViz 点目标小车会走 🎯 |
| Phase 3 | rosbridge 联通 | 0.5 天 | WebRop 看到真地图/真车 🎯 |
| Phase 4 | **路径跟随节点** | 1~2 天 | **画线小车跟走（Web 版核心复现）** 🎯🎯 |
| Phase 5 | 平滑跟踪（可选） | 1~2 天 | 丝滑跟曲线 |
| Phase 6 | 禁区+变速（可选） | 1 天 | 完整两论文功能 |
| **Part II — 接入 HoloLens2** | | | |
| Phase 7 | HL2 开发环境 | 1 天 | Unity+MRTK3 项目能建 |
| Phase 8 | ROS-TCP 桥 | 0.5 天 | Unity 发 goal 小车响应 🎯 |
| Phase 9 | HL2 手绘 UI | 2~3 天 | Unity 里画路径能发 🎯 |
| Phase 10 | QR 坐标对齐 | 1 天 | 画的路径落在正确 map 位置 |
| Phase 11 | 上机部署集成 | 1 天 | **戴头显画路径小车跟随（最终复现）** 🎯🎯🎯 |
| Phase 12 | 双客户端实验（可选） | 1 天 | 复现论文 MR vs 2D 对比 |
| **扩展功能** | | | |
| 扩展 | WebRop 同屏显示车 + HL2 | 1 天 | 平台看到两个实体位置 🎯 |

**Part I 最小可用（Web 版核心）：Phase 0~4，约 4~6 天。**
**Part I 完整（含平滑+禁区）：加 Phase 5~6，约 7~10 天。**
**Part II 接 HoloLens2（最终目标）：Phase 7~11，约 5~7 天。**
**全流程（两阶段全做完）：约 2~3 周。**
**加扩展（WebRop 显示 HL2 位置）：再加 1 天。**

---

## 整体交付物

- [ ] 一张可用的栅格地图（`maps/mymap.{yaml,pgm}`）
- [ ] `mrrep_bridge` catkin 包：`hrp_follower_node.py` + `mrrep_web.launch` + `mrrep_full.launch`
- [ ] **Part I 演示**：WebRop 画路径 → 小车跟随（录屏）
- [ ] HoloLens2 Unity 项目（MRTK3 + ROS-TCP-Connector + OpenXR QR）
- [ ] **Part II 演示**：戴头显地面画路径 → 小车跟随（录屏）
- [ ] （可选）自定义全局规划器插件源码
- [ ] （可选）双客户端对照实验数据
- [ ] （扩展）HL2 位姿发布器 + WebRop HL2 标记（同屏显示车 + HL2）
- [ ] 本计划书 + 踩坑记录

---

## 一句话总结

**机器人侧只认 `/hrp_path` 一个话题**——所以先用 WebRop（Part I，约一周）把机器人侧建图/导航/`hrp_follower_node` 整条链路调好，再上 HoloLens2（Part II，约一周）做 Unity MR 手绘客户端发同一个 `/hrp_path`。机器人侧代码两阶段零改动复用，最终戴头视画路径小车跟随，且顺带拥有论文 MR-vs-2D 实验的两种对照条件。**扩展功能再加 1 天，即可让 WebRop 平台同屏显示小车 + HoloLens2 两个实体位置**（HL2 发 `/hololens/pose`，WebRop 加一个订阅 + 一个标记，ROS 侧零改动）。
