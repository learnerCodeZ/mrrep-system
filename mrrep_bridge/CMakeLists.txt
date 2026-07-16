cmake_minimum_required(VERSION 3.0.2)
project(mrrep_bridge)

find_package(catkin REQUIRED COMPONENTS
  rospy
  std_msgs
  geometry_msgs
  nav_msgs
  move_base_msgs
  actionlib
  actionlib_msgs
)

catkin_package()

# 安装 Python 节点
catkin_install_python(PROGRAMS scripts/hrp_follower_node.py scripts/slam_bridge.py
  DESTINATION ${CATKIN_PACKAGE_BIN_DESTINATION}
)

# 安装 launch + config
install(DIRECTORY launch config
  DESTINATION ${CATKIN_PACKAGE_SHARE_DESTINATION}
)
