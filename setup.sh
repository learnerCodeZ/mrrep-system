#!/usr/bin/env bash
# ============================================================================
# mrrep-system setup.sh
# 在机器人 PC（Ubuntu 20.04 + ROS Noetic）上运行，拉取组件仓库 + 编译。
#
# 用法：
#   假定本仓库已 clone 到 ~/catkin_ws/src/mrrep-system
#   cd ~/catkin_ws/src/mrrep-system && bash setup.sh
#
# 为保证可复现，建议把下面的 *_BRANCH 改成具体 commit hash。
# ============================================================================
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CATKIN_SRC="$(dirname "$SCRIPT_DIR")"          # ~/catkin_ws/src
CATKIN_WS="$(dirname "$CATKIN_SRC")"            # ~/catkin_ws

echo "本仓库 : $SCRIPT_DIR"
echo "catkin : $CATKIN_WS"
echo "----------------------------------------------------------------"

# ---- 组件版本（可改成 commit hash 以固定可复现版本）----
EP_NAV_BRANCH=${EP_NAV_BRANCH:-main}            # 小车仓库
WEBROP_BRANCH=${WEBROP_BRANCH:-main}            # Web 平台
MRRP_HL2_BRANCH=${MRRP_HL2_BRANCH:-main}        # HL2 Unity 工程
ROS_TCP_BRANCH=${ROS_TCP_BRANCH:-main}          # ⚠️ main=ROS1, main-ros2=ROS2

clone_if_absent() {
  local url="$1" dest="$2" branch="$3"
  if [ -d "$dest/.git" ]; then
    echo "[skip] 已存在: $dest"
  else
    echo "[clone] $url -> $dest"
    git clone -b "$branch" "$url" "$dest"
  fi
}

# ---- 1. ROS catkin 包（放进 src，catkin_make 会一起编译）----
clone_if_absent https://github.com/learnerCodeZ/EP_navigation_Ros1.git \
                "$CATKIN_SRC/EP_navigation_Ros1" "$EP_NAV_BRANCH"

# ROS-TCP-Endpoint：Part II 给 HoloLens2 用（main 分支 = ROS1）
clone_if_absent https://github.com/Unity-Technologies/ROS-TCP-Endpoint.git \
                "$CATKIN_SRC/ROS-TCP-Endpoint" "$ROS_TCP_BRANCH"

# ---- 2. rosbridge（给 WebRop；apt 装，不是 clone）----
if ! rosdep pkg rosbridge_server >/dev/null 2>&1 && [ ! -d "/opt/ros/noetic/share/rosbridge_server" ]; then
  echo "[apt] 安装 rosbridge_suite（需要 sudo）"
  sudo apt update && sudo apt install -y ros-noetic-rosbridge-suite
fi

# ---- 3. 非 ROS 组件（clone 到 home，按需取用）----
clone_if_absent https://github.com/Harriet9410/WebRop.git \
                "$HOME/WebRop" "$WEBROP_BRANCH"

clone_if_absent https://github.com/learnerCodeZ/MRRP-Navigation.git \
                "$HOME/MRRP-Navigation" "$MRRP_HL2_BRANCH"

# ---- 4. 编译 ----
# mrrep_bridge 是本仓库子目录，catkin 会自动在 src 下发现它。
echo "----------------------------------------------------------------"
echo "[build] catkin_make ..."
cd "$CATKIN_WS"
catkin_make

echo "----------------------------------------------------------------"
echo "✅ 完成。下一步："
echo "   source $CATKIN_WS/devel/setup.bash"
echo "   # 先建图存图（maps/ 出厂为空）："
echo "   roslaunch rm_ep_navigation mapping.launch use_hi12:=true"
echo "   rosrun  rm_ep_navigation save_map.sh mymap"
echo "   # 再启动："
echo "   roslaunch mrrep_bridge mrrep_full.launch map_name:=mymap"
echo "----------------------------------------------------------------"
echo "WebRop     : $HOME/WebRop      （cd 进去 npm install && npm run dev）"
echo "MRRP-Navigation: $HOME/MRRP-Navigation （用 Unity 2022.3 LTS 打开）"
