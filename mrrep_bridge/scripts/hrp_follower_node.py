#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
hrp_follower_node.py
订阅 /hrp_path (nav_msgs/Path)，逐点喂给 move_base，让机器人按手绘折线跟随导航。

WebRop（经 rosbridge）和 HoloLens2（经 ROS-TCP）都发同一个 /hrp_path，
本节点不关心发送方，照单全收。

这是 MRReP "手绘路径 -> 机器人跟随" 在 ROS1/move_base 下的最小实现。
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
        # 收到新路径：若有正在执行的目标，先取消
        if self.busy:
            self.client.cancel_goal()
        self.path, self.idx = poses, 0
        rospy.loginfo("收到新路径，共 %d 个航点，frame=%s", len(poses), self.frame)
        self.send_next()

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
