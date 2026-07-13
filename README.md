# mrrep-system

> **MRReP 复现的系统整合仓库**：HoloLens2 手绘路径 → ROS1 小车导航 + Web 控制台。
>
> 本仓库代码很少，核心作用是**把三个组件仓库粘在一起**跑通 MRReP（arXiv:2604.00059）。机器人侧只认 `/hrp_path` 一个话题——这是整个系统的设计枢纽。

## 系统组成

| 组件 | 仓库 | 角色 | 技术栈 |
|---|---|---|---|
| 🚗 小车 | [EP_navigation_Ros1](https://github.com/learnerCodeZ/EP_navigation_Ros1) | 底盘驱动 + SLAM + AMCL + move_base（DJI RoboMaster EP） | ROS1 Noetic |
| 🥽 HL2 客户端 | [MRRP-Navigation](https://github.com/learnerCodeZ/MRRP-Navigation) | 手势画路径、QR 对齐、发路径到 ROS | Unity + MRTK |
| 🖥️ Web 平台 | [WebRop](https://github.com/Harriet9410/WebRop) | 浏览器画路径 + 监控（论文的 2D 基线） | React + Three.js + rosbridge |
| 🔧 **本仓库** | mrrep-system | 胶水：`hrp_follower_node` 路径跟随节点 + 一键启动 + 文档 | ROS1（`mrrep_bridge` 包） |

## 架构 / 数据流

```
[WebRop 浏览器] ──ws://IP:9090──┐                    ┌── tcp://IP:10000 ── [HoloLens2 Unity]
                                 ▼                    ▼
                       rosbridge_server  ← 并行 →  ros_tcp_endpoint
                                 ▼                    ▼
                            /hrp_path   (nav_msgs/Path, frame=map)
                            ← 两个客户端发同一个话题，机器人侧不关心来源 →
                                 ▼
                       hrp_follower_node.py     [本仓库 mrrep_bridge]
                                 ▼
                       /move_base_simple/goal → move_base → /cmd_vel → EP 底盘

                       /map ◀ map_server   /odom ◀ EKF   /scan ◀ rplidar   /tf ◀ AMCL
```

**核心设计**：`/hrp_path` 是统一接口。WebRop（rosbridge :9090）和 HoloLens2（ROS-TCP :10000）谁发都行，`hrp_follower_node` 照单全收、逐点喂 move_base。

## 快速开始

### 前置条件
- **机器人 PC**：Ubuntu 20.04 + ROS Noetic（同一局域网，记下 IP）
- **开发 PC**：Node 18+（跑 WebRop）、Unity 2022.3 LTS（开发 HL2）

### 1. 机器人侧（Ubuntu）—— 一次搭建
```bash
mkdir -p ~/catkin_ws/src && cd ~/catkin_ws/src
git clone https://github.com/learnerCodeZ/mrrep-system.git
cd mrrep-system && bash setup.sh        # 拉取三件套 + ROS-TCP-Endpoint + catkin_make
source ~/catkin_ws/devel/setup.bash
```
然后建图 + 存图（`maps/` 出厂为空，必须先建）：
```bash
roslaunch rm_ep_navigation mapping.launch use_hi12:=true     # 遥控走一圈
rosrun  rm_ep_navigation save_map.sh mymap
```

### 2. 跑起来
```bash
# Part I（Web 版，先跑通）：
roslaunch mrrep_bridge mrrep_web.launch  map_name:=mymap
# Part II（加 HoloLens2）：
roslaunch mrrep_bridge mrrep_full.launch map_name:=mymap
```

### 3. Web 侧（你的电脑）
```bash
git clone https://github.com/Harriet9410/WebRop.git
cd WebRop && npm install && npm run dev      # 浏览器开 http://localhost:3000
# WebRop 里把 rosbridge 地址改成 ws://机器人IP:9090，连上，画路径 → 发送
```

### 4. HL2 侧
见 [MRRP-Navigation](https://github.com/learnerCodeZ/MRRP-Navigation) 和 [docs/setup-guide.md](docs/setup-guide.md)。

## 目录结构

```
mrrep-system/
├── mrrep_bridge/                  胶水 ROS 包
│   ├── scripts/hrp_follower_node.py    /hrp_path → move_base 逐点跟随
│   └── launch/
│       ├── mrrep_web.launch            Part I（导航 + rosbridge + follower）
│       └── mrrep_full.launch           Part II（+ ros_tcp_endpoint 给 HL2）
├── docs/
│   ├── architecture.md                 架构与话题契约
│   └── setup-guide.md                  环境搭建详细步骤
├── setup.sh                            一键拉取组件 + 编译
├── .gitignore                          ROS + Unity + Node 三合一
└── README.md
```

## 复现路线（状态）

- [x] Part I 核心链路（WebRop → `/hrp_path` → `hrp_follower_node` → 小车）
- [ ] Part II：HoloLens2 接入（适配 MRRP-Navigation 的话题/坐标系，*待验证*）
- [ ] 扩展：WebRop 同屏显示 HoloLens2 位置（`/hololens/pose`）

> 详见 `plan/` 目录下的复现计划书。

## 论文
- MRReP — Mixed Reality-based Hand-drawn Reference Path Editing Interface（arXiv:2604.00059）
- MRHaD — Hand-drawn Restricted Zone Editing Interface（arXiv:2504.00580）
- 项目主页：https://mertcookimg.github.io/mrrep/

## License
MIT
