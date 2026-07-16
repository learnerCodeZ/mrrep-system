#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
despeckle_map.py —— 清除占用栅格 .pgm 里的孤立噪点（零星假障碍）。

gmapping 建图常会在地图里留下零星黑点（麦轮打滑 / 动态物 / 反光），它们被烤进静态地图，
导致 move_base 全局规划 和 WebRop 画路径都把它当墙挡路。本脚本把"孤立"的占据像素
（8 邻居里黑邻居太少）清成自由（白），保留连成片的真墙。

用法:
  python3 despeckle_map.py <map.pgm> [min_neighbors]
  rosrun  mrrep_bridge despeckle_map.py <map.pgm> [min_neighbors]

参数:
  map.pgm         地图 pgm 文件路径
  min_neighbors   孤立判定阈值，默认 2。黑像素 8 邻居里黑邻居 < 此值就清除。
                  调大清得更狠(3)，但可能啃掉细墙；默认 2 比较安全。

依赖: numpy, pillow   (sudo pip3 install numpy pillow  或 apt 装 python3-numpy python3-pil)

示例:
  cd ~/EP_navigation_Ros1/src/rm_ep_navigation/maps/实验室1
  python3 despeckle_map.py 实验室1.pgm
"""
import sys
import shutil
import numpy as np
from PIL import Image


def despeckle(src, min_nbr=2):
    arr = np.array(Image.open(src)).astype(np.int16)
    occ = arr < 50  # 黑 = 占据

    # 数每个像素 8 邻居里的黑邻居个数
    p = np.pad(occ.astype(np.int16), 1)
    nbr = np.zeros_like(occ, dtype=np.int16)
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            if dy == 0 and dx == 0:
                continue
            nbr += p[1 + dy:1 + dy + occ.shape[0], 1 + dx:1 + dx + occ.shape[1]]

    isolated = occ & (nbr < min_nbr)
    arr[isolated] = 254  # 清成白（自由）

    shutil.copyfile(src, src + ".bak")  # 先备份
    Image.fromarray(arr.astype(np.uint8)).save(src)
    return int(isolated.sum())


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    src = sys.argv[1]
    min_nbr = int(sys.argv[2]) if len(sys.argv) > 2 else 2
    n = despeckle(src, min_nbr)
    print(f"清除孤立噪点 {n} 个像素 (min_neighbors={min_nbr})")
    print(f"已备份 {src}.bak；不满意还原: mv {src}.bak {src}")
