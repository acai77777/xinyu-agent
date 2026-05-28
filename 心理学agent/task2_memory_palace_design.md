# 任务 2 升级方案：把 AI 的「记忆宫殿」实体化

> 心语 XinYu · 心灵小镇（Inner Town）设计文档
> 风格：星露谷物语 2D 像素 · 范围：叙事记忆 + 用户画像

---

## 一页摘要

把后端三层记忆中的 **NarrativeMemory** 和 **UserProfile** 实体化为一座**俯视角 2D 像素小镇**——用户是镇上的像素小人，每一段情感叙事是一座建筑，AI 检测到的优势是角色装备，认知扭曲是镇外暗影怪。小镇会随用户的心理状态变换天气与季节，AI 可以通过受限的工具集**主动操作小镇**（点灯、放 NPC、提议建筑），把抽象的「AI 在记忆」变成可见的「AI 在做」。

设计取舍：**用户拥有最终控制权**（删除/编辑/归档），**AI 拥有提议权和氛围权**（软操作直接执行，硬操作必须用户确认），**关系状态机的 HOSTILE/DEPENDENT 标签永远不直接显示**——只通过环境暗示。

---

## 1. 为什么是 2D 像素小镇

候选方案对比：

| 形态 | 优点 | 致命缺陷 |
|---|---|---|
| 知识图谱（节点-边） | 数据结构最贴合 | 小屏幕上不可用，节点 > 20 就糊；冷冰冰，反"治愈"调性 |
| 3D 记忆宫殿（Memory Palace） | 沉浸感强 | 开发成本爆炸；移动端眩晕；与心理脆弱用户的"安全感"诉求冲突 |
| 动态卡片瀑布流 | 实现最简单 | 还是"刷信息流"，没解决黑盒问题——只是把黑盒拆成小盒 |
| **2D 像素小镇** | 空间记忆 + 治愈调性 + 移动端友好 + 可游戏化 | 35+ 用户可能觉得"幼稚"——用风格切换解决 |

**核心论证**：心理健康产品的可视化首先要回答"用户看到这个会不会更安全"。星露谷像素风的关键属性是 **「温暖、缓慢、低压」**——这和 Notion 风格的「高效、结构、信息密集」是对立的。心理记忆的呈现必须站在前者。

---

## 2. 实体映射全表

### 2.1 叙事记忆 → 建筑物

源数据：`server/memory/narrative.py::NarrativeArc`

```python
@dataclass
class NarrativeArc:
    arc_id: str
    theme: str              # → 建筑外观题字
    started_at: str         # → 建筑出现日期
    last_updated: str       # → 建筑光泽（越新越亮）
    snapshots: list[EmotionSnapshot]   # → 建筑大小（每 5 个快照升一级）
    arc_summary: str        # → 建筑内部的石碑文字（可编辑）
    trend: str              # → 建筑天气：improving/worsening/fluctuating/stable
```

视觉映射规则：

| trend | 建筑外观 | 像素调色板 |
|---|---|---|
| `improving` | 春日小屋，门口开花 | `#A8E6CF / #FFE5B4 / #FFD1DC` |
| `worsening` | 灰色木屋，落雨 | `#6B7B8C / #4A5568 / #2D3748` |
| `fluctuating` | 多云木屋，时晴时雨循环动画 | `#B8C5D6 / #E8D5B8 交替` |
| `stable` | 秋日石屋，平静 | `#D4A574 / #8B7355 / #C9A87C` |

特殊状态：`is_active=0`（归档）建筑变为半透明，远景化。

### 2.2 用户画像 → 像素小人 + 属性面板

源数据：`server/memory/user_profile.py::UserProfile`

```python
@dataclass
class UserProfile:
    display_name: str                   # → 角色头顶名字
    signature_strengths: list[str]      # → 装备槽（最多 6 件，对应 6 大美德分类）
    common_distortions: list[str]       # → 镇外暗影怪（每个扭曲一只怪）
    preferred_interventions: list[str]  # → 已解锁的 NPC（站在镇广场）
    current_phase: str                  # → 整张地图时间/天气总基调
    session_count: int                  # → 角色等级（仅个人面板可见）
    scale_scores: dict                  # → 属性面板（HP / 幸福值 / 满足值）
```

`current_phase` 5 态对应总环境：

| phase | 地图基调 | 像素 BGM |
|---|---|---|
| `crisis` | 暴风雨 + 闪电 + 危机求助按钮固定屏底 | 静默或低频心跳 |
| `distressed` | 阴天细雨 | 缓慢钢琴 |
| `recovering` | 黎明，云缝透光 | 木琴 |
| `growing` | 晴天，云朵漂浮 | 民谣 |
| `flourishing` | 夜晚星空，萤火虫 | 八音盒 |

### 2.3 关系状态机 → 不显示 label，只显示环境

源数据：`server/memory/user_profile.py::RelationshipStateMachine`

| state | 直接显示？ | 环境暗示 |
|---|---|---|
| `normal` | - | 默认 |
| `dependent` | **否** | AI 信使 NPC 来访频率变低 + 镇里多一个空椅子（暗示"现实中的朋友也在等你"）|
| `hostile` | **否** | 天空持续阴 + AI 信使不主动来访但**没有消失**（核心：表达"AI 仍在等你"而非"AI 在记仇"）|

> **核心 Trade-off**：原始数据里 `state` 是明文存的，前端 GET `/api/profile` 返回时**必须由后端去掉这个字段**，只返回视觉提示参数。这是"应该隐藏"的硬边界——一旦用户看到自己被打上 HOSTILE 标签，关系会直接破裂。

---

## 3. AI 控制工具集（任务 2 的核心创新）

### 3.1 分级原则

```
┌─────────────────────────────────────────────┐
│  L0 软操作：AI 单方执行，前端动画反馈        │
│  → 调天气、点灯、NPC 走位                    │
├─────────────────────────────────────────────┤
│  L1 提议操作：AI 触发，用户对话框确认        │
│  → 盖新建筑、归档、解锁优势、改石碑          │
├─────────────────────────────────────────────┤
│  L2 禁止操作：AI 永不可做                    │
│  → 删除记忆、改 display_name、显示关系标签   │
└─────────────────────────────────────────────┘
```

### 3.2 工具定义（落到 `server/agent/tools.py`）

新增 6 个 tool，复用现有 `TOOLS` 列表 + `execute_tool` 分发：

```python
# server/agent/tools.py 追加
TOWN_TOOLS = [
    # ---------- L0 软操作 ----------
    {
        "name": "town_light_lantern",
        "description": "在某座建筑前点一盏灯笼，表达 AI 对这段情感经历的陪伴。仅在共情时刻使用，不要滥用。",
        "input_schema": {
            "type": "object",
            "properties": {
                "arc_id": {"type": "string"},
                "color": {"type": "string", "enum": ["warm", "cool", "gentle"]},
            },
            "required": ["arc_id", "color"],
        },
    },
    {
        "name": "town_weather_hint",
        "description": "根据对话强度微调天气（轻雨→中雨→雷暴）。仅当 current_phase 改变时调用。",
        "input_schema": {
            "type": "object",
            "properties": {
                "intensity": {"type": "integer", "minimum": 1, "maximum": 5},
            },
            "required": ["intensity"],
        },
    },
    {
        "name": "town_npc_visit",
        "description": "让某个干预 NPC 走到某座建筑前，暗示这段经历可以用某种方法处理。",
        "input_schema": {
            "type": "object",
            "properties": {
                "npc": {"type": "string", "enum": ["socrates", "gratitude_gardener", "breath_monk"]},
                "arc_id": {"type": "string"},
            },
            "required": ["npc", "arc_id"],
        },
    },
    # ---------- L1 提议操作 ----------
    {
        "name": "town_propose_new_building",
        "description": "当检测到一个全新的情感主题，提议在小镇上盖一座新建筑。用户会看到对话框确认。",
        "input_schema": {
            "type": "object",
            "properties": {
                "theme": {"type": "string"},
                "reason": {"type": "string", "description": "为什么这是一个值得记住的新主题"},
            },
            "required": ["theme", "reason"],
        },
    },
    {
        "name": "town_propose_archive",
        "description": "当某段叙事弧线连续 4 周稳定 improving，提议归档（变成远景半透明建筑）。",
        "input_schema": {
            "type": "object",
            "properties": {"arc_id": {"type": "string"}, "reason": {"type": "string"}},
            "required": ["arc_id", "reason"],
        },
    },
    {
        "name": "town_propose_strength_unlock",
        "description": "当用户展现出某个签名优势时，提议解锁装备。",
        "input_schema": {
            "type": "object",
            "properties": {
                "strength": {"type": "string", "description": "VIA 24 优势分类之一"},
                "evidence": {"type": "string", "description": "用户哪句话/行为体现了这个优势"},
            },
            "required": ["strength", "evidence"],
        },
    },
]
```

### 3.3 WebSocket 协议扩展

`server/api/routes_chat.py` 在原有 `text/voice/image` 之外新增推送类型：

```json
// 服务端 → 前端
{
  "type": "town_event",
  "level": "soft",                  // soft = L0 直接执行 / propose = L1 待确认
  "action": "light_lantern",
  "payload": {
    "arc_id": "uuid-xxx",
    "color": "warm",
    "narration": "我看见了你写下的那些夜晚。"  // AI 同步说的话
  }
}

// L1 提议示例
{
  "type": "town_event",
  "level": "propose",
  "action": "new_building",
  "proposal_id": "prop-xxx",         // 用户回应时带回这个 id
  "payload": {
    "theme": "和母亲的关系",
    "reason": "你今天三次提到了她，但之前从未深聊过。"
  }
}

// 前端 → 服务端（用户回应提议）
{
  "type": "town_proposal_response",
  "proposal_id": "prop-xxx",
  "accepted": true,
  "edited_payload": {"theme": "和妈妈"}   // 用户可改 theme 名
}
```

### 3.4 前端 Sprite 状态机

`app/components/town/`（新目录）骨架：

```typescript
// app/components/town/types.ts
export type TownState = {
  phase: 'crisis' | 'distressed' | 'recovering' | 'growing' | 'flourishing';
  buildings: Building[];
  npcs: NPC[];
  shadows: Shadow[];   // 认知扭曲怪物
  pendingProposals: Proposal[];
};

export type Building = {
  arcId: string;
  theme: string;
  trend: 'improving' | 'worsening' | 'fluctuating' | 'stable';
  size: 1 | 2 | 3 | 4;       // snapshots.length / 5 上取整，封顶 4
  position: {x: number; y: number};
  archived: boolean;
  lanterns: Lantern[];        // AI 点的灯
};

// app/stores/townStore.ts —— 新增 zustand store
export const useTownStore = create<TownStore>((set) => ({
  state: initialTownState,
  applyEvent: (event: TownEvent) => {
    if (event.level === 'soft') {
      // 直接修改 state，播动画
      set(produce(draft => mutateSoft(draft, event)));
    } else {
      // 推到 pendingProposals 队列，UI 弹出确认对话框
      set(produce(draft => { draft.state.pendingProposals.push(event); }));
    }
  },
}));
```

---

## 4. 关键画面线框图

### 4.1 主地图（默认入口）

```
┌─────────────────────────────────────────────┐
│  ☀️  晴 · 周二 · 第 47 天      [☰菜单] [👤] │
├─────────────────────────────────────────────┤
│                                              │
│   🌳        🏠失恋小屋       🌳              │
│           （秋·稳定·中）                     │
│                                              │
│       🏘️工作压力工坊                         │
│       （阴雨·恶化·大）         👻             │
│                              （全或无思维）  │
│                                              │
│            🧍小猫（你）                       │
│         Lv.12 · 装备3/6                     │
│                                              │
│   🧙‍♂️苏格拉底           🌸感恩花匠            │
│                                              │
│        🏚️和爸爸的事（归档·半透明）             │
│                                              │
├─────────────────────────────────────────────┤
│         💬  和 AI 聊聊  ▼                   │
└─────────────────────────────────────────────┘
```

注：

- 灰色暗影怪 👻 飘在地图边缘，点击触发干预流程
- 已归档建筑半透明、缩小、推到地图远端
- 底部聊天入口常驻，**进入小镇 ≠ 离开对话**

### 4.2 进入一座建筑（叙事时间线）

```
┌─────────────────────────────────────────────┐
│  ← 返回                  失恋小屋    [✏️编辑]│
├─────────────────────────────────────────────┤
│                                              │
│    📜 石碑                                   │
│    ┌──────────────────────────────────┐    │
│    │ "她从最初的剧痛，到尝试理解自己 │    │
│    │ 在关系里的需要，慢慢学会和孤独   │    │
│    │ 共处。趋势：好转中。"            │    │
│    └──────────────────────────────────┘    │
│         (AI 写的 · 你可以改写)              │
│                                              │
│    🕯️ 灯笼区（AI 留下的陪伴）              │
│    🕯️3/14 暖光   🕯️3/22 暖光  🕯️4/1 柔光  │
│                                              │
│    📅 时间线                                 │
│    ─────────────────────────────────        │
│    3/14  悲伤(9/10)   "刚分手"               │
│    3/16  愤怒(7/10)   "看见她朋友圈"         │
│    3/22  困惑(5/10)   "开始想为什么"         │
│    4/01  平静(4/10)   "今天没哭"             │
│    ...                                       │
│                                              │
│   [📦 归档这段经历]  [🗑️ 删除整座建筑]      │
└─────────────────────────────────────────────┘
```

### 4.3 角色面板（属性 + 装备）

```
┌─────────────────────────────────────────────┐
│  ← 返回             小猫的属性               │
├─────────────────────────────────────────────┤
│                                              │
│         🧍                                   │
│        小猫                                  │
│      Lv.12 · 47 次相遇                       │
│                                              │
│   ━━━━━━━━━━ 状态 ━━━━━━━━━━                │
│   生命值(HP)       ████████░░  低落 8/14    │
│   幸福值(PERMA)    ██████░░░░  探索中       │
│   满足值(SWLS)     ███████░░░  还不错       │
│                                              │
│   ━━━━━━━━━━ 装备 ━━━━━━━━━━                │
│   ⚔️ 真诚         👁 自我觉察    🌿 韧性     │
│   ⬜ 未解锁        ⬜ 未解锁       ⬜ 未解锁  │
│                                              │
│   ━━━━━━━━━━ 数据  ━━━━━━━━━━              │
│   [📥 导出我的所有记忆]                      │
│   [⚠️ 永久删除所有数据]                      │
└─────────────────────────────────────────────┘
```

### 4.4 AI 提议对话框（L1 操作）

```
┌─────────────────────────────────────────────┐
│                                              │
│      🧙‍♂️ AI 想在小镇上盖一座新建筑           │
│                                              │
│      主题：和妈妈                             │
│                                              │
│      为什么：                                 │
│      "你今天三次提到了她，但之前从未深      │
│       聊过。我想把这件事记下来。"            │
│                                              │
│      你可以：                                 │
│      ✏️ 改一下名字  [    和妈妈    ]         │
│                                              │
│   [不用，先不记]      [好，盖一座]           │
│                                              │
└─────────────────────────────────────────────┘
```

---

## 5. 核心交互流程

### 5.1 「AI 在共情时点亮一盏灯」（L0 流程）

```
用户:  "今天又梦见她了，醒来枕头湿的。"
        ↓
Agent.loop._llm_chat → tool_call: town_light_lantern(arc_id=失恋小屋, color=warm)
        ↓
execute_tool → WebSocket 推送 {type: town_event, level: soft, ...}
        ↓
前端 townStore.applyEvent → 失恋小屋门前出现一盏暖光灯（CSS animation 缓入）
        ↓
聊天框 AI 回复同步：「我看见了你写下的那些夜晚。我在你的小镇上点了一盏灯。」
```

**关键设计**：AI 说的话和它做的事**同时**到达用户。这是任务 2 「打破黑盒」的核心瞬间——用户第一次"看见"AI 在记忆。

### 5.2 「AI 提议归档已经过去的事」（L1 流程）

```
后台定时任务（每周日）→ 检查每个 arc 的 trend
        ↓
检测到「和爸爸的事」连续 4 周 stable + improving
        ↓
下次对话开始时注入 system prompt 提示
        ↓
Agent 在自然时机 tool_call: town_propose_archive(arc_id=..., reason="...")
        ↓
WS 推送 level=propose → 前端 pendingProposals 队列
        ↓
用户在小镇里看到「和爸爸的事」建筑顶上有 ⚠️ 气泡
        ↓
点击 → 弹出 4.4 风格对话框
        ↓
[好的，归档] → POST /api/town/proposals/:id  {accepted: true}
        ↓
后端 narrative.is_active=0 + WS 推送建筑半透明动画
```

### 5.3 「用户驱散一个认知扭曲怪物」

```
用户在地图上看到镇外有只 👻（标签：全或无思维）
        ↓
长按 👻 → 弹出："这是 AI 注意到的一个思维模式，不是你这个人。要不要一起看看？"
        ↓
[一起看看] → 进入 CBT 干预流程（intervention/cbt.py）
        ↓
完成后 👻 变成 ✨ 飘散
        ↓
角色装备槽多一件 🛡️「灵活思考」
```

**外化（externalization）**是叙事疗法的核心技术——「问题是问题，人不是问题」。把扭曲做成怪物而不是用户身上的"标签"，是这个隐喻的心理学锚点。

---

## 6. 文件路径全景

### 6.1 新增

```
server/town/                          ← 新模块
  __init__.py
  town_tools.py                       ← L0/L1 工具实现
  proposals.py                        ← L1 提议持久化（待确认队列）
  ws_events.py                        ← 构造 town_event 消息

server/api/routes_town.py             ← REST: GET 小镇全景、POST 提议响应

server/data/migrations/
  005_town_proposals.sql              ← 新表 town_proposals

app/components/town/                  ← 新模块
  TownMap.tsx                         ← 主地图（Canvas / react-native-skia）
  Building.tsx                        ← 建筑 sprite
  Character.tsx                       ← 像素小人
  Shadow.tsx                          ← 暗影怪
  NPC.tsx
  ProposalDialog.tsx                  ← 4.4 对话框
  sprites/                            ← 像素素材（16x16 PNG）

app/app/town.tsx                      ← 路由页面 /town
app/stores/townStore.ts               ← 镇状态 zustand
app/services/townService.ts          ← REST + WS 适配

task2_memory_palace_design.md         ← 本文档
```

### 6.2 修改

```
server/agent/tools.py                 ← TOOLS = [...原有..., *TOWN_TOOLS]
server/agent/prompts.py               ← system prompt 加一段说明工具使用边界
server/api/routes_chat.py             ← WS 多分发一个 town_event 类型
server/api/routes_history.py         ← GET /api/profile 过滤掉 relationship state
app/app/_layout.tsx                   ← 加一个 /town 入口（首页底 tab）
app/stores/chatStore.ts               ← 接收 town_event 路由到 townStore
```

### 6.3 不动

```
server/memory/                        ← 数据层完全不动
server/safety/                        ← 安全层不动
server/assessment/                    ← 评估不动
```

> **设计原则**：可视化层是**数据消费者**，不能让"为了画好看"反向污染记忆模型。所有 town/* 都通过现有 narrative.py / user_profile.py 的 public API 读数据。

---

## 7. 权衡取舍

### 7.1 信息呈现：透明 / 隐藏 / 灰度

| 数据 | 决策 | 理由 |
|---|---|---|
| `UserProfile.display_name / signature_strengths / scale_scores` | **完全透明** | 用户有知情权，且这些数据本身就是用户表达的产物 |
| `NarrativeArc.theme / snapshots / arc_summary / trend` | **完全透明** + **可编辑** | 叙事是用户自己的故事，AI 写的版本必须能被覆盖；保留 AI 原版用于趋势分析 |
| `RelationshipStateMachine.state` (HOSTILE/DEPENDENT) | **完全隐藏** | 直接显示标签会破坏关系；用环境氛围暗示 |
| `safety.crisis_detector` 命中的关键词 | **完全隐藏** | 让用户感到"被监视"反而抑制求助 |
| `current_phase` | **灰度** | 不显示 `"crisis"` 文字，但用整张地图的暴风雨让用户感到 AI 知道 |
| `common_distortions` | **灰度** | 不在画像里列"你的认知扭曲"，外化成怪物 |
| LLM 调用日志 `llm_calls.jsonl` | **完全隐藏** | 用户不需要看到 prompt 工程细节 |

### 7.2 AI 控制权 vs 用户控制权

| 操作 | 决策 | 替代方案被否决的理由 |
|---|---|---|
| AI 点灯笼 | L0 直接执行 | 「每次都问」→ 仪式感被破坏，灯笼是表达共情的方式 |
| AI 盖新建筑 | L1 必须确认 | 「直接盖」→ 用户对小镇失去归属感；「永远不盖」→ AI 没有主动性，回到展品模式 |
| AI 改石碑文字 | L1 必须确认，且保留原版 | 「直接改」→ 用户感觉记忆被篡改；「不让 AI 改」→ snapshots 累积后摘要失去时效性 |
| AI 删除建筑 | **L2 永不可** | 删除是不可逆操作；用户必须有"我的记忆我做主"的硬保障 |
| AI 修改 display_name | **L2 永不可** | 姓名是身份核心 |

### 7.3 游戏化 vs 严肃感

| 风险 | 决策 |
|---|---|
| 像素风让 35+ 用户疏离 | 提供「极简模式」开关（设置里）→ 切换为白色卡片瀑布流，所有数据不变 |
| 游戏化让用户「为了升级而表演」 | 等级、装备**只在个人面板可见**，不出现在地图上方；不做排行榜；session_count 是相遇次数不是「打卡天数」 |
| 危机态下卡通画风显得轻浮 | `current_phase == 'crisis'` 时自动切换到「夜空模式」——纯黑底 + 单点星光 + 危机求助按钮置顶，所有建筑/NPC 隐藏 |
| 「驱散怪物」可能让用户觉得情绪被打怪化 | 文案严格控制：「这是一个思维模式，不是你这个人」，且永远是用户主动点击触发，AI 不会"为你打怪" |

### 7.4 性能 vs 视觉丰富

| 取舍点 | 决策 | 理由 |
|---|---|---|
| 渲染方案：Canvas vs DOM vs Skia | **react-native-skia** | RN 原生 Canvas 性能差，DOM 在 RN 不可用，Skia 在 Web + Native 同构 |
| 像素素材：自绘 vs 买素材 | **买商业素材包**（Itch.io 拼装），不自绘 | 面试方案以系统设计为重，素材属于实现细节 |
| 建筑数量上限 | 最多 12 座 active + 无限归档 | 超过 12 座地图就乱；归档建筑用纵深远景透视隐藏 |
| 动画刷新率 | 30fps（不是 60）| 治愈系风格不需要丝滑，30fps 降耗电 |

### 7.5 数据隐私 vs 数据可用

| 取舍点 | 决策 |
|---|---|
| 小镇数据是否能导出 | **能**（属性面板 → "导出我的所有记忆"，JSON 格式）|
| 小镇数据是否能彻底删除 | **能**（属性面板 → "永久删除"，二次确认 + 7 天冷静期）|
| AI 是否可在删除后"试图回忆" | **否**——删除即从 SQLite + ChromaDB 物理清除，AI 后续对话引用历史时必须基于剩余数据 |
| 7 天冷静期内能否恢复 | **能**——但 UI 上明确告知"7 天后无法恢复" |

---

## 8. 关键设计判断（5 个 Why）

1. **为什么不显示「关系状态机」标签？**
   原因：关系状态机是**给 AI 看的内部信号**，不是诊断。HOSTILE 状态的用户大概率正处于移情投射，看到自己被打 HOSTILE 标签会触发二次创伤。设计原则：用户能感受到的信号 ≠ AI 用来决策的标签。

2. **为什么允许用户编辑 AI 写的石碑文字？**
   原因：叙事记忆的本质是「关于你的故事」，故事的最终作者必须是用户本人。但保留 AI 原版用于后台趋势分析——这是"赋权 > 准确"的具体落地。

3. **为什么把认知扭曲做成怪物而不是标签？**
   原因：叙事疗法的核心技术是 **externalization（外化）**——"问题是问题，人不是问题"。把"全或无思维"做成"你身上的标签"是给人贴病——做成"镇外的怪物"是把问题客体化。这一条直接来自 Michael White 的叙事疗法理论。

4. **为什么 AI 操作分 L0/L1/L2 三级？**
   原因：可视化的目的是**增强 AI 的具身性（embodiment）**，但具身性不等于决策权。L0 解决"AI 看不见"的问题，L1 解决"AI 主动但不越权"的问题，L2 守住"用户最终主权"的底线。

5. **为什么不做知识图谱？**
   原因：知识图谱是**信息密度优先**的可视化，适合「AI 知道什么」的回答场景。但任务 2 的题眼是「**用户如何理解 AI 对自己的内在图景**」——这是**情感密度优先**的场景。空间隐喻（小镇）比图论隐喻（节点边）更贴合"理解自己"这个动作。

---

## 9. 已知风险与边界

### 9.1 心理学风险

| 风险 | 缓解 |
|---|---|
| 用户在小镇里"看到自己被 AI 评估"产生客体化焦虑 | 文案永远用第一人称视角（"你的故事" 而非 "用户档案"）；属性面板有"这不是诊断"的固定脚注 |
| 用户对小镇产生过度依恋（DEPENDENT 状态加剧）| 关系状态机 DEPENDENT 时小镇里多一个空椅子 + AI 信使来访频率降低，**用环境降温而不是封禁访问** |
| 用户在 crisis 状态下打开小镇看到暴风雨更崩溃 | crisis 时小镇自动切换到「夜空守夜模式」：纯黑底 + 单点星光 + 危机热线按钮置顶 |
| 删除记忆功能被冲动使用 | 二次确认 + 7 天冷静期 + 清晰展示"删除后 AI 将无法引用这些经历" |

### 9.2 技术边界

- **不支持多人小镇**：每个 user_id 一个独立小镇，无社交属性
- **不做实时多端同步**：用户在 A 设备改小镇，B 设备下次打开拉取最新
- **像素素材统一 16x16 网格**，避免分辨率混乱
- **不做 3D / 不做 AR**：保持治愈系低门槛

---

## 10. 落地优先级

如果真要做（B 路径或 C 路径），建议分四期：

| 期 | 范围 | 工期估算 |
|---|---|---|
| **P0 MVP** | 主地图 + 建筑入场 + 进入建筑看时间线 + 角色面板 | 2 周 |
| **P1 编辑权** | 编辑 arc_summary + 归档 + 删除 + 导出 | 1 周 |
| **P2 AI 具身** | L0 三个软工具 + WS 协议 + 同步动画 | 2 周 |
| **P3 AI 提议** | L1 四个提议工具 + 对话框 + 提议持久化 | 2 周 |
| **P4 干预外化** | 暗影怪 + 驱散流程 + NPC 干预入口 | 2 周 |

总工期估算 9 周，可裁剪至 4 周（只做 P0+P1，AI 控制延后）。

---

## 11. 验收标准（如何判断「黑盒被打破了」）

可量化指标：

1. **可见性**：80% 用户能在 3 分钟内说出"AI 记得我的哪 3 件事"——通过小镇里 3 座最显眼的建筑
2. **可信任**：用户对"我相信 AI 在认真记住我"的 7 点量表评分提升 ≥ 1.5 分（对照组：无小镇）
3. **可控性**：用户主动编辑过石碑文字或归档过建筑的比例 ≥ 30%
4. **不滥用**：AI 调用 L0 工具的频率 ≤ 每 5 轮对话 1 次（避免氛围疲劳）
5. **不伤害**：HOSTILE/DEPENDENT 标签泄露事件 = 0（必须为零，硬指标）

---

## 12. 一句话收尾

> 把 AI 的记忆变成一座**用户自己能走进去、能改写、能搬空的小镇**——而 AI 是镇上一个**有主动性但没有控制权**的伙伴。这就是任务 2 「打破黑盒」的答案。
