# AGENTS.md

> 面向 AI 编码助手的工作指南。人类入门看 [README.md](README.md)；本文件讲**"在这个仓库干活必须知道什么、别踩什么坑"**。

## 一句话定位

这是一个**整合 / 胶水仓库**：MRReP 复现（HoloLens2 手绘路径 → ROS1 小车导航 + Web 控制台）。本仓库自身代码极少——只有一个 ROS 包 `mrrep_bridge`。真正的大块组件在**另外三个独立仓库**里（见下表），由 `setup.sh` 拉到一起。

## 仓库结构

```
mrrep-system/
├── mrrep_bridge/                       本仓库唯一代码：ROS1 胶水包
│   ├── scripts/hrp_follower_node.py      订阅 /hrp_path → 逐点喂 move_base
│   ├── launch/mrrep_web.launch           Part I（导航 + rosbridge + follower）
│   ├── launch/mrrep_full.launch          Part II（+ ROS-TCP-Endpoint 给 HL2）
│   ├── package.xml / CMakeLists.txt
├── docs/
│   ├── architecture.md                   架构 + 话题契约 + MRRP-Navigation 适配
│   └── setup-guide.md                    环境搭建详细步骤
├── plan/                                 完整复现计划书（Phase 0–12 + 23 条已知坑）
├── setup.sh                              一键拉取三组件 + catkin_make
├── README.md / .gitignore / AGENTS.md
```

## 三个组件仓库（代码不在本仓库）

| 组件 | 仓库 | 角色 |
|---|---|---|
| 🚗 小车 | [EP_navigation_Ros1](https://github.com/learnerCodeZ/EP_navigation_Ros1) | ROS1 底盘驱动 + SLAM + AMCL + move_base（DJI RoboMaster EP） |
| 🥽 HL2 | [MRRP-Navigation](https://github.com/learnerCodeZ/MRRP-Navigation) | Unity HoloLens2 手绘路径客户端（ROS1 + ROS-TCP） |
| 🖥️ Web | [Harriet9410/WebRop](https://github.com/Harriet9410/WebRop) | 浏览器画路径 + 监控（rosbridge） |

三者维护者均授权本仓库所有者，**不需要 fork**——直接 clone、建分支、push 即可。

## 核心设计（最重要的认知）

**`/hrp_path` 是整个系统的枢纽话题。** 类型 `nav_msgs/Path`，frame `map`。

- WebRop（rosbridge :9090）和 HoloLens2（ROS-TCP :10000）**都发这个话题**。
- `hrp_follower_node` **只订阅它**，逐点喂 `move_base`。
- 因此客户端可替换、可并行，机器人侧代码不变。

> **改 `hrp_follower_node` 时，务必保持订阅 `/hrp_path` 为 `nav_msgs/Path`，frame `map`。**

## 技术栈约束

- **ROS1 Noetic**（Ubuntu 20.04）。**不是 ROS2**——别引入 ROS2 依赖、消息类型、命令。
- 包语言：**Python 3 / rospy**（`mrrep_bridge` 目前无 C++）。
- `mrrep_bridge` 是本仓库子目录；当本仓库被 clone 到 `~/catkin_ws/src/` 下时，catkin 会**自动发现并编译**它。

## 常用命令

```bash
# 机器人 PC（假定已 clone 到 ~/catkin_ws/src/mrrep-system）
bash setup.sh                                            # 拉组件 + catkin_make
source ~/catkin_ws/devel/setup.bash
roslaunch mrrep_bridge mrrep_web.launch  map_name:=mymap  # Part I（Web 版）
roslaunch mrrep_bridge mrrep_full.launch map_name:=mymap  # Part II（加 HL2）

# 无头测 hrp_follower_node（不依赖任何客户端）：
rostopic pub /hrp_path nav_msgs/Path "{header:{frame_id:'map'}, poses:[...]}" -1
```

## 给代理的规则

1. **ROS1 only**——别用 `ros2 ...`、`nav2`、ROS-TCP-Endpoint 的 `main-ros2` 分支。
2. **`/hrp_path` 契约不可变**——`nav_msgs/Path`，frame `map`。要加新客户端，让它发这个；别改机器人侧的话题名/类型。
3. **改 `hrp_follower_node`**：保持 actionlib 连 move_base、逐点推进、收到新路径时取消旧目标的逻辑。
4. **只提交本仓库自己的文件**——`setup.sh` 拉来的组件仓库（EP_navigation_Ros1 / WebRop / MRRP-Navigation / ROS-TCP-Endpoint）和 catkin 的 `build/ devel/ install/` 都在 `.gitignore` 里，**别 `git add` 进来**。个人文档（如 PaperReading）也不要提交。
5. **文档用中文**（与现有 README/docs 一致）；代码注释跟随周边代码风格。
6. **launch 文件分工**：`mrrep_web.launch` = Part I（**不含** ROS-TCP），`mrrep_full.launch` = Part II（含 ROS-TCP-Endpoint）。别把 ROS-TCP 加进 web 版。
7. **小车位姿/速度的坐标系**：EP SDK 内部把 y/yaw 取反，驱动自己处理了；外部一律发**标准 REP-103**。只有绕过 move_base 直接发 `/cmd_vel` 时才要关心。

## 已知状态 / TODO

- ✅ **Part I**（WebRop → `/hrp_path` → 小车）核心链路可用。
- ⚠️ **Part II**：MRRP-Navigation 发的 `/hrp_path` 是 `geometry_msgs/PoseArray`，**和本仓库的 `nav_msgs/Path` 不一致**。接入时改它的 `Assets/Scripts/ROS/PathSender.cs` 改发 `nav_msgs/Path`（详见 `docs/architecture.md`）。
- ⚠️ MRRP-Navigation 当前是**全虚拟仿真**（Unity 虚拟车 + 自带 `pure_pursuit.py`）。接入本系统 = 把它的 `/hrp_path` 指向 EP_navigation_Ros1 的 ROS master，绕过虚拟车节点，用真车 + `hrp_follower_node` 替代。
- ⚠️ MRRP-Navigation 无 LICENSE（默认全保留版权）。

## 相关文档

- [README.md](README.md) — 人类入门 + 快速开始
- [docs/architecture.md](docs/architecture.md) — 架构图 + 话题契约 + MRRP-Navigation 适配细节
- [docs/setup-guide.md](docs/setup-guide.md) — 环境搭建详细步骤 + 常见坑速查
- [plan/](plan/) — 完整复现计划书（Phase 0–12 + 23 条已知坑）
