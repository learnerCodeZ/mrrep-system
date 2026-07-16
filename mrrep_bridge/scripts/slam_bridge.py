#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
slam_bridge.py
监听 /webrop/slam_command (std_msgs/String)，让 WebRop 能触发机器人侧建图控制。

WebRop 的 SlamPanel 发的命令：
  - "start:方法:设备"  → 开始建图（map 模式下 gmapping 已由 launch 起好，此处仅提示）
  - "stop"             → 停止并存图（调 rm_ep_navigation 的 save_map.sh）
  - "save" / "save:名字"→ 存图

本节点只在 map 模式有意义（gmapping 必须在跑）。
"""
import datetime
import rospy
import subprocess
from std_msgs.msg import String


def save_map(name=None):
    try:
        pkg = subprocess.check_output(["rospack", "find", "rm_ep_navigation"]).decode().strip()
    except Exception as e:  # noqa
        rospy.logerr("找不到 rm_ep_navigation 包: %s", e)
        return
    script = pkg + "/scripts/save_map.sh"
    if not name:
        name = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    rospy.loginfo("存图: bash %s %s", script, name)
    ret = subprocess.call(["bash", script, name])
    rospy.loginfo("存图完成 (ret=%d)。地图在 %s/maps/%s/", ret, pkg, name)


def cb(msg):
    cmd = (msg.data or "").strip()
    low = cmd.lower()
    rospy.loginfo("收到 /webrop/slam_command: '%s'", cmd)
    if "stop" in low or low.startswith("save"):
        name = None
        if ":" in cmd:
            name = cmd.split(":", 1)[1].strip() or None
        save_map(name)
    elif low.startswith("start"):
        rospy.loginfo("建图应由 map 模式启动 (mode:=map)；gmapping 若在跑则继续。")
    else:
        rospy.logwarn("未知 slam 命令 '%s'（支持 stop / save / save:名字）", cmd)


if __name__ == "__main__":
    rospy.init_node("slam_bridge")
    rospy.Subscriber("/webrop/slam_command", String, cb, queue_size=1)
    rospy.loginfo("slam_bridge 就绪：监听 /webrop/slam_command（stop/save → 调 save_map.sh 存图）")
    rospy.spin()
