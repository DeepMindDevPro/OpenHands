# OpenHands Token 变化可视化 — 深度评估报告

## 一、一次完整对话中Token变化的完整生命周期

### 1.1 一次对话的事件流全景

```
用户发消息 → WebSocket → Agent Server(SDK)
  │
  ├── Step 1: 组装系统提示 (system_prompt.j2 + skills + tools)
  │     → [token: system_prompt_tokens]
  │
  ├── Step 2: 获取事件历史 → event_store.get_events()
  │     → [token: 所有历史event的token总和 = prompt_tokens_so_far]
  │
  ├── Step 3: 上下文压缩 → condenser.condense(events)
  │     ├── 未超max_size(240) → 直接透传
  │     └── 超过max_size → LLM摘要旧事件 + 保留最近窗口
  │           → CondensationEvent(forgotten_event_ids, summary)
  │           → [token: prompt_tokens骤降!]
  │           → [额外消耗: condenser prompt_tokens]
  │
  ├── Step 4: 调用LLM → LLM.completion(messages, tools)
  │     → ConversationStateUpdateEvent(key="stats")
  │        ├── agent.accumulated_token_usage.prompt_tokens (累积)
  │        ├── agent.accumulated_token_usage.completion_tokens (累积)
  │        ├── agent.accumulated_token_usage.per_turn_token (本轮)
  │        ├── agent.accumulated_token_usage.context_window (模型上限)
  │        ├── agent.token_usages[] ← ⚠️ 每轮独立的TokenUsage列表!
  │        └── condenser.accumulated_token_usage.prompt_tokens (压缩消耗)
  │
  ├── Step 5: 执行工具 → 新ObservationEvent加入事件存储
  │     → [token: 上下文增长]
  │
  └── 回到Step 2 (循环)
```

### 1.2 Token变化的典型曲线

```
prompt_tokens (累积)
  ↑
  │                                              ╱─╲
  │                                         ╱─╲ ╱   ╲
  │                                    ╱─╲ ╱   ╲     ╲
  │          ╱─╲                 ╱─╲ ╱   ╲     ╲     ╲
  │     ╱─╲ ╱   ╲     ╱─╲ ╱─╲ ╱   ╲     ╲     ╲     ╲
  │╱─╲ ╱   ╲     ╲ ╱   ╲     ╲     ╲     ╲     ╲     ╲
  │   ╲     ╲   [压缩!]╲   [压缩!]   ╲   [压缩!]   ╲
  │    ╲     ╲   ↗╲     ╲   ↗╲        ╲   ↗╲        ╲
  │     ╲     ╲ ╱  ╲     ╲ ╱  ╲        ╲ ╱  ╲        ╲
  └────────────────────────────────────────────────────→ turn
     1  2  3  4  5  6  7  8  9 10 11 12 13 14 15 16 17

  关键特征：
  - 每轮：prompt_tokens单调递增（新event追加）
  - 压缩点：prompt_tokens骤降（旧事件被摘要替代）
  - 压缩后增速更快（因为新event持续追加）
  - context_window是水平线（模型上限，如128k）
```

### 1.3 关键发现：SDK已携带逐轮Token数据但被丢弃

通过深入分析 `conversation-state-event.ts` 中的 `LLMMetrics` 接口：

```typescript
export interface LLMMetrics {
  model_name: string;
  accumulated_cost: number;
  max_budget_per_task: number | null;
  accumulated_token_usage: TokenUsage;     // ← 累积值（当前被使用）
  costs: Array<{ model, cost, timestamp }>; // ← 逐轮成本列表
  response_latencies: Array<{ model, latency, response_id }>; // ← 逐轮延迟
  token_usages: TokenUsage[];               // ← ⚠️ 逐轮独立TokenUsage列表!
}
```

**核心发现**：SDK的`LLMMetrics`中 **`token_usages: TokenUsage[]`** 已经包含了每轮独立的TokenUsage快照（含`per_turn_token`, `prompt_tokens`, `response_id`等），但当前：
- 后端 `update_conversation_statistics()` 只提取了 `accumulated_token_usage`（累积值），**丢弃了 `token_usages[]`**
- 前端 `updateMetricsFromStats()` 也只取 `accumulated_token_usage`，**丢弃了 `token_usages[]`**

---

## 二、之前的方案评估——5个关键缺陷

### 缺陷1：忽略SDK已有的逐轮数据

之前方案建议新增`TokenSnapshot`表逐条插入，但SDK的`LLMMetrics.token_usages[]`已经包含逐轮数据，不需要重新采集，只需要**保留而不是丢弃**。

### 缺陷2：未区分agent和condenser两条独立的token曲线

`usage_to_metrics`包含两个独立的`LLMMetrics`：
- `agent`：主推理LLM的token消耗
- `condenser`：压缩LLM的token消耗

两条曲线应**同图展示**，condenser的token消耗标注在压缩点附近。

### 缺陷3：未处理CondensationEvent与stats事件的关联

压缩发生时会产生两个独立事件：
1. `CondensationEvent`（标记哪些事件被遗忘+摘要内容）
2. 紧随其后的 `ConversationStateUpdateEvent(key="stats")`（prompt_tokens骤降）

需要在时间线上**关联**这两个事件，才能展示"压缩前→压缩后"的token降幅。

### 缺陷4：未考虑costs[]和response_latencies[]的复用

`LLMMetrics.costs[]`和`response_latencies[]`也是逐轮数据，可直接用于：
- 成本随轮次的变化曲线
- 响应延迟随轮次的变化曲线

### 缺陷5：前端metrics-store只存快照，丢失时序

`metrics-store.ts` 用Zustand只存最新快照：

```typescript
const useMetricsStore = create<MetricsStore>((set) => ({
  cost: null, usage: null,  // ← 每次set覆盖，无历史
  setMetrics: (metrics) => set(metrics),
}));
```

需要改为**追加模式**，累积token_usages序列。

---

## 三、修正后的完整改造方案

### 3.1 数据层：保留SDK已有的逐轮数据（3处改动）

**A. 后端：存储token_usages序列**

在 `StoredConversationMetadata` 新增JSON列：

```python
# 新增列（migration）
token_timeline: Mapped[list[dict] | None] = mapped_column(
    create_json_type_decorator(list[dict]), nullable=True
)
# 每条记录: {turn, timestamp, prompt_tokens, completion_tokens, per_turn_token,
#            context_window, response_id, is_condensed, condenser_prompt_tokens}
```

在 `update_conversation_statistics()` 中追加而不是丢弃：

```python
# 提取token_usages[]和costs[]
if agent_metrics.token_usages:
    new_entries = []
    for tu in agent_metrics.token_usages:
        new_entries.append({
            "turn": len(stored.token_timeline or []) + len(new_entries) + 1,
            "timestamp": tu.timestamp if hasattr(tu, 'timestamp') else None,
            "prompt_tokens": tu.prompt_tokens,
            "completion_tokens": tu.completion_tokens,
            "per_turn_token": tu.per_turn_token,
            "context_window": tu.context_window,
            "response_id": tu.response_id,
        })
    stored.token_timeline = (stored.token_timeline or []) + new_entries
```

**B. 后端：关联CondensationEvent与stats事件**

在 `on_event()` 中标记压缩轮次：

```python
# 检测CondensationEvent
condensed_this_batch = False
for event in events:
    if hasattr(event, 'forgotten_event_ids'):  # CondensationEvent
        condensed_this_batch = True
        # 可提取: event.forgotten_event_ids, event.summary

for event in events:
    if isinstance(event, ConversationStateUpdateEvent) and event.key == 'stats':
        await app_conversation_info_service.process_stats_event(
            event, conversation_id, is_condensed=condensed_this_batch
        )
```

**C. 后端：新增API端点**

```
GET /api/conversations/{id}/token-timeline
Response: {
  timeline: [{
    turn, timestamp,
    prompt_tokens, completion_tokens, per_turn_token, context_window,
    is_condensed, condenser_prompt_tokens,
    forgotten_count,  // 压缩时被遗忘的事件数
  }],
  condensation_details: [{  // 压缩详情
    turn, summary, forgotten_event_ids_count
  }]
}
```

### 3.2 前端数据层：从快照到时序（2处改动）

**A. 重构 metrics-store → token-timeline-store**

新增 `token-timeline-store.ts`：

```typescript
interface TokenTimelineEntry {
  turn: number;
  timestamp: string;
  prompt_tokens: number;
  completion_tokens: number;
  per_turn_token: number;
  context_window: number;
  is_condensed: boolean;
  condenser_prompt_tokens: number | null;
  response_id: string;
}

interface TokenTimelineStore {
  entries: TokenTimelineEntry[];
  condensationDetails: Array<{
    turn: number;
    summary: string;
    forgottenCount: number;
  }>;
  addEntries: (entries: TokenTimelineEntry[]) => void;
  reset: () => void;
}
```

**B. 修改WebSocket事件处理**

在 `updateMetricsFromStats()` 中追加时序数据：

```typescript
const updateMetricsFromStats = useCallback((event) => {
  if (event.value.usage_to_metrics?.agent) {
    const agentMetrics = event.value.usage_to_metrics.agent;

    // 保留现有行为：更新累积快照
    useMetricsStore.getState().setMetrics({...});

    // 新增：追加逐轮数据到timeline
    if (agentMetrics.token_usages?.length) {
      const newEntries = agentMetrics.token_usages.map((tu, i) => ({
        turn: useTokenTimelineStore.getState().entries.length + i + 1,
        timestamp: new Date().toISOString(),
        prompt_tokens: tu.prompt_tokens,
        completion_tokens: tu.completion_tokens,
        per_turn_token: tu.per_turn_token,
        context_window: tu.context_window,
        is_condensed: false,  // 由CondensationEvent联动设置
        condenser_prompt_tokens: null,
        response_id: tu.response_id,
      }));
      useTokenTimelineStore.getState().addEntries(newEntries);
    }

    // 新增：condenser的token消耗
    const condenserMetrics = event.value.usage_to_metrics?.condenser;
    if (condenserMetrics?.accumulated_token_usage) {
      // 标记最后一轮为condensed
    }
  }
}, []);
```

### 3.3 前端可视化层：4个核心组件

**组件1：`TokenTimelineChart` — 主折线图（双Y轴）**

```
┌─────────────────────────────────────────────────────────┐
│  Token 变化时间线                                        │
├─────────────────────────────────────────────────────────┤
│ prompt_tokens                                            │
│  ↑     ╱╲        ╱╲╱╲           ╱╲╱╲╱╲                │
│  │   ╱    ╲     ╱     ╲        ╱       ╲               │
│  │ ╱     [🔴]╱        ╲     [🔴]        ╲              │
│  │╱      ↙╱            ╲   ↙╱             ╲            │
│  ┼────────────────────────────────────────────→ turn    │
│  │  context_window ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─         │
│  │  (128k水平虚线)                                       │
│  │                                                       │
│  │  ▓▓▓ condenser消耗 (红色竖条, 仅在压缩轮出现)        │
├─────────────────────────────────────────────────────────┤
│ 使用率: per_turn_token / context_window                  │
│  ↑ ▓▓▓▓▓░░░░ ▓▓▓▓▓▓░░░░ ▓▓▓▓▓▓▓▓░░░ ▓▓▓▓▓░░         │
│  0%──────────────────────────────────────100%           │
└─────────────────────────────────────────────────────────┘

图例：
  蓝色实线 = agent prompt_tokens（累积）
  绿色面积 = 使用率 (per_turn_token/context_window)
  红色竖线+标记 = CondensationEvent发生点
  红色竖条 = condenser prompt_tokens（压缩消耗）
  灰色虚线 = context_window上限
```

**组件2：`CondensationDetail` — 压缩详情卡片**

点击红色标记时弹出：

```
┌──────────────────────────────────────┐
│ 🔄 第5轮压缩                         │
│                                      │
│ 压缩前: prompt_tokens = 95,234       │
│ 压缩后: prompt_tokens = 42,108       │
│ 降幅:   -53,126 (-55.8%)             │
│                                      │
│ 被遗忘事件: 47条                      │
│ 摘要: "用户要求修改login.py的认证     │
│  逻辑，已执行了3次文件编辑..."        │
│                                      │
│ Condenser消耗: 2,847 prompt_tokens   │
└──────────────────────────────────────┘
```

**组件3：`ContextWindowGauge` — 实时仪表盘**

替换当前简单的进度条，嵌入 `ContextWindowSection`：

```
┌────────────────────────────────────┐
│  上下文窗口  ████████░░░░  67.3%  │
│  86,150 / 128,000 tokens          │
│  ⚠ 距离下次压缩约 12 轮           │
│  (max_size=240, 当前198事件)       │
└────────────────────────────────────┘
```

**组件4：`ChatCondensationMarker` — 聊天流内联标记**

在聊天事件流中，`CondensationEvent`位置插入：

```
── 🔄 上下文已压缩 · 47条历史事件被摘要 ──────────────
   [点击查看摘要详情]
──────────────────────────────────────────────────────
```

### 3.4 完整改动清单与评估

| # | 层级 | 改动 | 文件 | 工作量 | 风险 |
|---|------|------|------|--------|------|
| 1 | DB | 新增token_timeline JSON列 + migration | sql_app_conversation_info_service.py + alembic | 0.5天 | 低 |
| 2 | 后端 | update_conversation_statistics保留token_usages | sql_app_conversation_info_service.py | 0.5天 | 低 |
| 3 | 后端 | on_event关联CondensationEvent标记 | webhook_router.py | 0.5天 | 低 |
| 4 | 后端 | 新增GET /token-timeline API | 新文件 | 0.5天 | 低 |
| 5 | 前端 | 新增token-timeline-store | 新文件 stores/ | 0.5天 | 低 |
| 6 | 前端 | 修改updateMetricsFromStats追加时序 | conversation-websocket-context.tsx | 0.5天 | 中 |
| 7 | 前端 | TokenTimelineChart组件 | 新文件 components/ | 1.5天 | 低 |
| 8 | 前端 | CondensationDetail组件 | 新文件 | 0.5天 | 低 |
| 9 | 前端 | ContextWindowGauge替换进度条 | context-window-section.tsx | 0.5天 | 低 |
| 10 | 前端 | ChatCondensationMarker | chat事件渲染 | 0.5天 | 低 |
| 11 | 前端 | MetricsModal集成Tab | metrics-modal.tsx | 0.5天 | 低 |
| **合计** | | **11处改动** | **~10文件** | **6-7天** | **低-中** |

### 3.5 关键设计决策

1. **优先复用SDK已有的`token_usages[]`**，而非重新采集 — 减少后端改动量，避免数据不一致
2. **双源数据**：实时场景用前端store累积`token_usages[]`（WebSocket推送），历史场景用后端API（持久化后查询）
3. **CondensationEvent与stats事件通过turn序号关联**，而非时间戳（避免时钟偏差）
4. **condenser消耗独立展示**，让用户理解压缩本身的成本
5. **渐进式上线**：先做数据采集(1-4)→再做实时可视化(5-7)→最后做交互细节(8-11)

---

## 四、之前方案遗漏的3个深层次问题

### 问题1：token_usages[]的覆盖语义

SDK的`LLMMetrics.token_usages[]`是**累积列表还是每轮增量？** 当前Webhook每批次推送时，stats事件中的`token_usages[]`可能包含多轮数据（batch推送），需要去重（通过`response_id`判重）。

### 问题2：CondensationEvent的时间顺序

Agent Server推送事件是batch模式（一次推送多个event），`CondensationEvent`和`ConversationStateUpdateEvent(key="stats")`在同一批次中的顺序不确定。需要通过event timestamp或turn序号对齐。

### 问题3：对话重连时的时序恢复

前端WebSocket断开重连时，需要从后端API重新加载完整的`token_timeline`，而非仅依赖store中的累积数据。因此后端持久化是必须的。
