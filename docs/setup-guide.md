# 环境搭建详细步骤

## 总览：两台机器

| 机器 | 跑什么 | 系统 |
|---|---|---|
| **机器人 PC**（Jetson/Ubuntu 台式机） | ROS1 Noetic + 小车驱动 + 导航 + rosbridge + ROS-TCP-Endpoint + `hrp_follower_node` | Ubuntu 20.04 |
| **开发 PC**（你的电脑） | WebRop（Node）、Unity 开发 HL2 | Windows/Mac |

两台在同一局域网。机器人 PC 记下 IP（`hostname -I`），假设 `192.168.1.50`。

---

## 一、机器人 PC（Ubuntu 20.04 + ROS Noetic）

### 1. 装 ROS Noetic
按 http://wiki.ros.org/noetic/Installation/Ubuntu 装。确保 `source /opt/ros/noetic/setup.bash` 在 `~/.bashrc` 里。

### 2. 搭 catkin 工作区 + 拉组件
```bash
mkdir -p ~/catkin_ws/src && cd ~/catkin_ws/src
git clone https://github.com/learnerCodeZ/mrrep-system.git
cd mrrep-system && bash setup.sh        # 自动拉取 EP_navigation_Ros1 / ROS-TCP-Endpoint / WebRop / MRRP-Navigation + catkin_make
source ~/catkin_ws/devel/setup.bash
```
> `setup.sh` 会把 `mrrep_bridge`（本仓库子目录）一并编译——catkin 自动发现 src 下的包。

### 3. 建图（maps/ 出厂为空，必须先建）
```bash
roslaunch rm_ep_navigation mapping.launch use_hi12:=true   # 终端1
rosrun  rm_ep_driver ep_teleop_keyboard.py                 # 终端2，遥控走一圈
rosrun  rm_ep_navigation save_map.sh mymap                 # 终端3，存图
```
⚠️ `use_hi12:=true`（外置 HI12 九轴 IMU）是默认且承重的，给磁力计稳定航向。

### 4. 网络
- 放行端口：`sudo ufw allow 9090 && sudo ufw allow 10000`（或 `sudo ufw disable` 测试用）。
- 确认 rosbridge 监听 0.0.0.0：启动后 `ss -tlnp | grep 9090` 应是 `0.0.0.0:9090`。

### 5. 启动
```bash
# Part I（先跑通 Web 版）：
roslaunch mrrep_bridge mrrep_web.launch map_name:=mymap
# Part II（加 HoloLens2）：
roslaunch mrrep_bridge mrrep_full.launch map_name:=mymap
```

---

## 二、开发 PC —— WebRop

```bash
git clone https://github.com/Harriet9410/WebRop.git
cd WebRop && npm install && npm run dev      # http://localhost:3000
```
浏览器里：Mock 关掉 → rosbridge 地址改 `ws://192.168.1.50:9090` → 连接 → 画路径 → 发送。

---

## 三、开发 PC —— HoloLens2（MRRP-Navigation）⚠️ 待验证

### 工具链红线
- **Unity 2022.3 LTS**（如 2022.3.22f1）。Unity 2025-06-23 后移除 HL2 支持，**Unity 6/2023 不能用**。
- VS 2022（UWP + C++ workload + USB connectivity）、Win10 SDK 10.0.19041、Mixed Reality Feature Tool。
- MRTK3 + `com.microsoft.mixedreality.openxr` + ROS-TCP-Connector。

### 打开 MRRP-Navigation
```bash
# setup.sh 已 clone 到 ~/MRRP-Navigation（或你手动 clone）
```
用 Unity 2022.3 LTS 打开该工程。

### TODO（等 MRRP-Navigation 评估结论）
- [ ] 确认它是 ROS1 还是 ROS2（若 ROS2，ROS-TCP-Endpoint 要切 `main-ros2` 分支，或转 rosbridge）
- [ ] 确认它发的话题名 —— 对齐到 `/hrp_path`（`nav_msgs/Path`，frame=`map`）
- [ ] 确认坐标系（Unity 左手/Y上 ↔ ROS map 右手/Z上 的轴映射，靠 QR 对齐）
- [ ] QR 用 Microsoft OpenXR QR（不用已废弃的 Vuforia）

### 部署到 HL2
- Unity Build Settings → UWP / ARM64 / D3D / IL2CPP / .NET Standard 2.1。
- Capabilities 必勾：`InternetClient`、`InternetClientServer`、`PrivateNetworkClientServer`、`Webcam`、`SpatialPerception`。
- Build 出 `.sln` → VS 2022 ARM64/Release 部署（USB 首次需 PIN 配对）。

---

## 四、验证清单

- [ ] RViz "2D Nav Goal" 小车会走（move_base 全栈 OK）
- [ ] WebRop 连上能看到真地图 + 真车（`/map`、`/odom` 通）
- [ ] WebRop 画路径 → 小车沿形状走（**Part I 核心**）
- [ ] Unity 里发 `/hrp_path` → 小车跟随（Part II 通信通）
- [ ] 戴 HL2 地面画路径 → 小车跟随（**最终复现**）

---

## 常见坑速查
- `maps/` 空 → 先建图存图。
- rosbridge 只绑 127.0.0.1 → 局域网连不上，确认 0.0.0.0。
- HL2 socket 连上但消息不通 → ROS-TCP-Endpoint 分支选错（`main`=ROS1）或 Unity Protocol 设错。
- EP 默认 SN 锁死 → `ep_sn:=` / `ep_ip:=` 覆盖。
- 详细“已知坑”清单见 `../plan/` 下的复现计划书（共 23 条）。
