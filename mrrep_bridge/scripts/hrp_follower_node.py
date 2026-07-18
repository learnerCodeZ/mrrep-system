#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
hrp_follower_node.py
订阅 /hrp_path (nav_msgs/Path)，逐点喂给 move_base，让机器人按手绘折线跟随导航。

WebRop（经 rosbridge）和 HoloLens2（经 ROS-TCP）都发同一个 /hrp_path，
本节点不关心发送方，照单全收。

这是 MRReP "手绘路径 -> 机器人跟随" 在 ROS1/move_base 下的最小实现。
"""
import math
import rospy
import actionlib
from nav_msgs.msg import Path
from geometry_msgs.msg import Quaternion
from move_base_msgs.msg import MoveBaseAction, MoveBaseGoal
from actionlib_msgs.msg import GoalStatus


class HrpFollower:
    def __init__(self):
        self.path, self.idx, self.busy, self.frame = [], 0, False, "map"
        # 航点降采样间距(m)：避免密点(< move_base xy_goal_tolerance=0.2)导致反复到达/抖动；可参数调
        self.min_spacing = rospy.get_param("~min_spacing", 0.3)

        self.client = actionlib.SimpleActionClient("move_base", MoveBaseAction)
        rospy.loginfo("等待 move_base action server ...")
        # 不死等，避免 navigation.launch 还没起好时阻塞
        if not self.client.wait_for_server(rospy.Duration(10.0)):
            rospy.logwarn("10s 内未连上 move_base，继续等待（确认 navigation.launch 已启动）")
        rospy.loginfo("move_base 已连上。")

        rospy.Subscriber("/hrp_path", Path, self.cb_path, queue_size=1)
        rospy.loginfo("已订阅 /hrp_path。在 WebRop / HoloLens2 里画路径并发送即可。")

    def cb_path(self, msg):
        poses = list(msg.poses)
        if len(poses) < 2:
            rospy.logwarn("路径点数 < 2，忽略。")
            return
        self.frame = msg.header.frame_id or "map"
        # 降采样：航点间距 >= min_spacing，避免密点(< xy_goal_tolerance)让 move_base 反复到达/抖动
        poses = self.downsample(poses, self.min_spacing)
        # 航点朝向：每个点指向下一个点，到达时车头朝向可控
        poses = self.assign_orientations(poses)
        # 收到新路径：若有正在执行的目标，先取消
        if self.busy:
            self.client.cancel_goal()
        self.path, self.idx = poses, 0
        rospy.loginfo("收到新路径，降采样后 %d 个航点（间距≥%.2fm），frame=%s",
                      len(poses), self.min_spacing, self.frame)
        self.send_next()

    def downsample(self, poses, min_spacing):
        """按累计间距降采样：保留首点、末点、以及距上一个保留点 ≥ min_spacing 的点。"""
        if len(poses) <= 2:
            return poses
        keep = [poses[0]]
        for p in poses[1:-1]:
            last = keep[-1].pose.position
            cur = p.pose.position
            if math.hypot(cur.x - last.x, cur.y - last.y) >= min_spacing:
                keep.append(p)
        # 末点必保留（用原始末点，保证到达精确终点）
        last_pt = poses[-1].pose.position
        prev = keep[-1].pose.position
        if math.hypot(last_pt.x - prev.x, last_pt.y - prev.y) >= 1e-3:
            keep.append(poses[-1])
        else:
            keep[-1] = poses[-1]
        return keep

    def assign_orientations(self, poses):
        """每个航点朝向设为指向下一个航点(2D yaw)；末点沿用上一段方向。"""
        for i in range(len(poses) - 1):
            dx = poses[i + 1].pose.position.x - poses[i].pose.position.x
            dy = poses[i + 1].pose.position.y - poses[i].pose.position.y
            yaw = math.atan2(dy, dx)
            poses[i].pose.orientation = Quaternion(0.0, 0.0, math.sin(yaw / 2.0), math.cos(yaw / 2.0))
        if len(poses) >= 2:
            poses[-1].pose.orientation = poses[-2].pose.orientation
        return poses

    def send_next(self):
        if self.idx >= len(self.path):
            rospy.loginfo("✅ 路径全部执行完成。")
            self.busy = False
            return
        self.busy = True
        goal = MoveBaseGoal()
        goal.target_pose = self.path[self.idx]
        goal.target_pose.header.frame_id = self.frame
        goal.target_pose.header.stamp = rospy.Time.now()
        rospy.loginfo("→ 前往航点 %d/%d", self.idx + 1, len(self.path))
        self.client.send_goal(goal, done_cb=self.cb_done)

    def cb_done(self, status, result):
        if status == GoalStatus.SUCCEEDED:
            rospy.loginfo("  航点 %d 到达。", self.idx + 1)
            self.idx += 1
            self.send_next()
        elif status in (GoalStatus.ABORTED, GoalStatus.REJECTED):
            rospy.logwarn("  航点 %d 失败(status=%d)，跳过。", self.idx + 1, status)
            self.idx += 1
            self.send_next()
        elif status == GoalStatus.PREEMPTED:
            rospy.loginfo("  航点 %d 被取消（收到新路径）。", self.idx + 1)
            self.busy = False
        else:
            rospy.logwarn("  航点 %d 状态=%d", self.idx + 1, status)
            self.idx += 1
            self.send_next()


if __name__ == "__main__":
    rospy.init_node("hrp_follower_node")
    HrpFollower()
    rospy.spin()
