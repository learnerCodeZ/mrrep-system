# 计划（暂存）：WebRop ↔ Unity 共享路径协同编辑

> **状态**：🅿️ 暂存（待执行）。2026-07-18 提出，先留底，主流任务（HL2 复现）推进后再做。
> **目标**：Unity（HoloLens2）和 WebRop **同时操控同一段路径**；WebRop 作为控制台，能**发布 / 停止 / 清除**。
> **背景**：当前 Unity 一发 `/hrp_path` 就直接驱车，WebRop 插不上手；WebRop 只能"看"（已加红色叠显）。本计划让两者**协同编辑同一条草稿路径**，由 WebRop 统一控制执行。

---

## 1. 核心思路：草稿 / 执行 分离

把"草稿路径"和"执行路径"拆成两个话题：

- **`/hrp_draft`（共享草稿）**：WebRop 和 Unity 都能在上面画/改，**实时互相同步**。车不动。
- **`/hrp_path`（执行）**：只有 WebRop 点"发布"时，草稿才复制过去 → `hrp_follower_node` → 车。
- **WebRop = 控制台**：发布 / 停止 / 清除 都在 WebRop。Unity = 草稿输入端（画完进草稿，不直接驱车）。

> 效果：Unity 画线先**进草稿**，WebRop 看着满意了点"发布"才执行；不满意能"停止"（车停）/"清除"（清空草稿）。

---

## 2. 话题结构

| 话题 | 类型 | 作用 | 备注 |
|---|---|---|---|
| `/hrp_draft` | `nav_msgs/Path`（**latched**） | 共享草稿，双方 pub+sub | latched：迟到者拿到当前草稿 |
| `/hrp_path` | `nav_msgs/Path` | 执行 → `hrp_follower_node`（不变） | 只 WebRop"发布"写 |
| `/move_base/cancel` | `actionlib_msgs/GoalID` | 停止（取消当前导航） | WebRop 已有 `cancelNavGoal` |

---

## 3. 各端职责

### WebRop（控制台 + 编辑器）
- 现有 HRP 编辑器 = 草稿编辑器；每次改动 pub 到 `/hrp_draft`。
- 订阅 `/hrp_draft`：收到 Unity 的草稿 → 合并/替换进显示。
- 三个控制按钮：
  - **发布**：当前草稿 → `/hrp_path`（hrp_follower 执行）。
  - **停止**：`cancelNavGoal`（取消 move_base，车停）。
  - **清除**：发空 `/hrp_draft`（双方草稿清空）+ 可选停止。

### Unity（草稿输入端）
- 画线 → 发 **`/hrp_draft`**（不再直接发 `/hrp_path`）。
- 车相对合成仍在 Unity：`PathSender` 把画的形状盖到车位姿后发草稿（绝对 map 坐标）。
- 订阅 `/hrp_draft`：显示共享草稿（戴头显的人能看到 WebRop 的修改）——可选，Unity 侧要加渲染。

### 机器人侧
- 不变：`hrp_follower_node` 订阅 `/hrp_path`，逐点喂 move_base（已含降采样 + 朝向）。

---

## 4. 编辑模型（关键选择，做前先定）

- **替换（last-writer-wins）**：谁后画谁覆盖整条草稿。简单。适合"一人主画、一人微调"。**推荐先做。**
- **追加（append）**：每次画作为一段拼到共享路径。适合"两人接力画长路径"，需要协议（段标识/序号），复杂。

> 建议：先实现**替换**模型，够用后再升级**追加**。

---

## 5. 坐标一致性（实现注意）

- `/hrp_draft` 统一存**绝对 map 坐标**：
  - Unity 画 → 车相对合成（PathSender 现有逻辑）→ 绝对 map → 发 `/hrp_draft`。
  - WebRop 画 → scene 坐标 → 反向 `rosToScene`（scene→map）→ 绝对 map → 发 `/hrp_draft`。
- 双方显示都用 `rosToScene`（map→scene），一致。
- WebRop"发布"只做 draft → `/hrp_path` 的**转发**，不做坐标转换。

---

## 6. 三个粒度（按工作量）

| 级别 | 内容 | 工作量 | 何时做 |
|---|---|---|---|
| **L1 最小** | WebRop 加"停止/清除"按钮（停=`cancelNavGoal`，清除=清显示）；Unity 仍直接发 `/hrp_path`。只给 WebRop 加控制权，不改 Unity。 | 小（纯 WebRop） | 想立刻能停/清时 |
| **L2 共享草稿** | 完整方案：`/hrp_draft` 双向同步 + 发布/停止/清除；Unity 改发草稿。真正"同时操控同一段路径"。 | 中（WebRop + Unity） | 主目标 |
| **L3 ROS 路径服务器** | ROS 节点持权威路径，service 增删改（add_point/clear/publish）；最稳、支持多人并发。 | 大 | 一般不需要 |

---

## 7. 推荐

- **主目标 = L2**（你要的"同时操控 + WebRop 控发布/停/清"）。
- 可**先快做 L1**（约半小时，WebRop 立刻能停/清 Unity 发的路径、立即见效），再升级 L2。
- L3 暂跳过。

---

## 8. L2 改动清单（执行时参照）

### WebRop
- [ ] `connection.ts`：加 `/hrp_draft` 的 pub + sub（nav_msgs/Path）。
- [ ] 草稿 store（或复用 `navPlanStore.hrpPath` 作为草稿源）。
- [ ] HRP 编辑器改动 → pub `/hrp_draft`；收 `/hrp_draft` → 更新编辑器/显示。
- [ ] UI 三按钮：**发布**（draft→`/hrp_path`）/ **停止**（cancelNavGoal）/ **清除**（发空 draft + 清显示）。
- [ ] 发布按钮：转发 draft，不动坐标。

### Unity
- [ ] `PathSender.cs`：改发 `/hrp_draft`（车相对合成后），不再发 `/hrp_path`。
- [ ] （可选）加 `/hrp_draft` 订阅 + 渲染，显示共享草稿（让 HL2 看到 WebRop 改动）。
- [ ] `PreferredPathMenuController` 的 `P` 键 / SEND 流程改为发草稿。

### 机器人侧
- [ ] 无改动（`hrp_follower_node` 仍订阅 `/hrp_path`）。

---

## 9. 待确认（执行前）

1. 做 **L1 还是 L2**？
2. 编辑模型 **替换 还是 追加**？
3. Unity 是否需要**显示共享草稿**（HL2 看 WebRop 改动）？还是只做单向（Unity 发、WebRop 控）？

---

**一句话**：草稿（`/hrp_draft`，共享双向）与执行（`/hrp_path`）分离，WebRop 当控制台（发布/停止/清除），Unity 当草稿输入端；先做 L1 见效、再上 L2 真协同。
