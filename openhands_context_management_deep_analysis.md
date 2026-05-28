# OpenHands 上下文管理模块深度分析

## 一、总体架构概览

OpenHands 的上下文管理采用了**分层、可插拔、事件驱动**的架构设计，核心围绕 AI Agent 对话过程中"上下文窗口有限"这一根本矛盾展开。整个上下文管理系统可分为以下几个核心层次：

```
┌─────────────────────────────────────────────────────────┐
│                   前端展示层 (React)                      │
│  ContextWindowSection / CondensationEvent 展示            │
├─────────────────────────────────────────────────────────┤
│                App Server 对话管理层                       │
│  LiveStatusAppConversationService                        │
│  AppConversationServiceBase (Condenser 构建)             │
│  AgentContext 构建 (skills/secrets/suffix)               │
├─────────────────────────────────────────────────────────┤
│              SDK 核心上下文管理层 (openhands-sdk)          │
│  Agent / AgentContext / CondenserBase                    │
│  LLMSummarizingCondenser / Event                         │
│  ConversationState / ConversationSettings                │
├─────────────────────────────────────────────────────────┤
│               事件持久化层 (EventService)                 │
│  FilesystemEventService / AwsEventService               │
│  GoogleCloudEventService (Enterprise)                    │
├─────────────────────────────────────────────────────────┤
│             对话元数据持久化层 (SQL)                       │
│  SQLAppConversationInfoService                           │
│  StoredConversationMetadata (context_window/token统计)   │
└─────────────────────────────────────────────────────────┘
```

---

## 二、核心组件详解

### 2.1 AgentContext — 上下文容器

**位置**: `openhands.sdk.context.AgentContext`（SDK 外部包）

**核心职责**: 作为 Agent 运行时的上下文容器，承载 Agent 执行过程中所需的全部附加信息。

**关键字段**（从源码使用推导）:

| 字段 | 类型 | 说明 |
|------|------|------|
| `skills` | `list[Skill]` | Agent 可用的技能列表 |
| `secrets` | `dict[str, SecretSource]` | 敏感凭据（API Key、Token 等） |
| `system_message_suffix` | `str` | 附加到系统提示末尾的后缀文本 |

**构建流程**（在 [`LiveStatusAppConversationService._build_start_conversation_request_for_user()`](openhands/app_server/app_conversation/live_status_app_conversation_service.py:1262) 中）:

```python
# 构建 AgentContext 实例
agent_context = AgentContext(
    system_message_suffix=effective_suffix,  # 包含规划Agent指令 + WEB_HOST 上下文
    secrets=secrets,                          # Git Provider Token + 用户自定义 Secrets
)
```

**ACP Agent 场景**: 对 ACP 子进程型 Agent，AgentContext 用于向 ACP prompt 渲染 `<CUSTOM_SECRETS>` 块，并将 Secret 值注入子进程环境变量（SDK PR #2984 支持）。

**Skills 合并机制**: 在 [`_create_agent_with_skills()`](openhands/app_server/app_conversation/app_conversation_service_base.py:159) 中：

```python
def _create_agent_with_skills(self, agent, skills):
    if agent.agent_context:
        # 合并已有 skills，新 skills 覆盖同名旧 skills
        existing_skills = agent.agent_context.skills
        all_skills = self._merge_skills([existing_skills, skills])
        agent = agent.model_copy(update={
            'agent_context': agent.agent_context.model_copy(
                update={'skills': all_skills}
            )
        })
    else:
        agent_context = AgentContext(skills=skills)
        agent = agent.model_copy(update={'agent_context': agent_context})
    return agent
```

---

### 2.2 Condenser — 上下文压缩引擎

**位置**: `openhands.sdk` 中的 `LLMSummarizingCondenser`（SDK 外部包），本地镜像参考 [`mini-openhands-gen/generate_all.py:389`](mini-openhands-gen/generate_all.py:389)

#### 2.2.1 Condenser 抽象体系

```
CondenserBase (ABC)
├── NoopCondenser          — 无压缩，直接透传
├── RecentCondenser        — 保留最近 N 个事件，丢弃旧事件
└── LLMSummarizingCondenser — LLM 摘要压缩：旧事件 → 摘要 + 最近事件
```

#### 2.2.2 LLMSummarizingCondenser 核心机制

**SDK 默认参数**: `max_size=240, keep_first=2`

**工作流程**:

1. **触发条件**: 当事件数量超过 `max_size` 阈值时触发压缩
2. **分割策略**: 将事件列表分为"旧事件"（待摘要）和"最近窗口事件"（保留原文）
3. **LLM 摘要**: 将旧事件构建为文本，调用 LLM 生成摘要
4. **重组**: `CondensationEvent(summary) + recent_events`

**异常恢复**: 如果 LLM 摘要失败，回退到截断策略：
```python
return f"Context compressed (summarization failed): {len(events)} events removed"
```

#### 2.2.3 Condenser 的构建和配置

在 [`AppConversationServiceBase._create_condenser()`](openhands/app_server/app_conversation/app_conversation_service_base.py:459) 中：

```python
def _create_condenser(self, llm, agent_type, condenser_max_size):
    condenser_kwargs = {
        'llm': llm.model_copy(update={
            'usage_id': 'condenser' if agent_type == DEFAULT else 'planning_condenser'
        }),
    }
    # 仅当用户自定义 max_size 时覆盖 SDK 默认值
    if condenser_max_size is not None:
        condenser_kwargs['max_size'] = condenser_max_size
    return LLMSummarizingCondenser(**condenser_kwargs)
```

**关键设计决策**:
- Condenser 使用独立的 LLM 实例（从 Agent LLM 复制），带独立的 `usage_id` 用于追踪
- Planning Agent 的 Condenser 标记为 `planning_condenser`，用于区分计费和分析
- Condenser LLM 追踪元数据在 [`_apply_server_agent_overrides()`](openhands/app_server/app_conversation/live_status_app_conversation_service.py:1092) 中注入

#### 2.2.4 上下文溢出的三层异常恢复

在 Agent.step() 循环中（参考 [`mini-openhands-gen/step3_agent_main.py:350`](mini-openhands-gen/step3_agent_main.py:350)），实现了三层异常恢复链：

```
异常链 1: FunctionCallValidation → 将错误反馈给 LLM 重试
异常链 2: MalformedHistory → 强制 Condenser 压缩上下文 (RecentCondenser max=20)
异常链 3: ContextLengthExceeded → 极端降级 (RecentCondenser max=5)
```

---

### 2.3 Event — 上下文的基本单元

**位置**: `openhands.sdk.Event`（SDK 外部包）

Event 是上下文管理的基本数据单元。整个对话历史由 Event 序列构成，Condenser 操作的对象就是 Event 列表。

#### 2.3.1 Event 类型体系

```
Event (SDK 基类)
├── MessageEvent         — 用户/助手消息
├── ActionEvent          — Agent 执行的动作
├── ObservationEvent     — 动作的执行结果
├── CondensationEvent    — 上下文压缩事件
│   ├── forgotten_event_ids  — 被遗忘（从LLM视图中移除）的事件ID列表
│   ├── summary              — 可选的被遗忘事件摘要
│   └── summary_offset       — 摘要插入位置偏移量
├── CondensationRequestEvent — 请求上下文压缩
├── CondensationSummaryEvent — 压缩器生成的摘要
└── ConversationStateUpdateEvent — 对话状态更新
    └── key="stats" → TokenUsage (context_window, per_turn_token)
```

#### 2.3.2 CondensationEvent 在前端的表现

前端通过 [`condensation-event.ts`](frontend/src/types/v1/core/events/condensation-event.ts) 定义了三种事件类型，用于向用户展示上下文压缩过程：
- `CondensationEvent`: 告知正在压缩，标记哪些事件被"遗忘"
- `CondensationRequestEvent`: 请求压缩
- `CondensationSummaryEvent`: 展示摘要内容

---

### 2.4 ConversationSettings — 对话配置容器

**位置**: `openhands.sdk.settings.ConversationSettings`（SDK 外部包）

承载对话级别的配置参数，在 [`settings_models.py`](openhands/app_server/settings/settings_models.py:75) 中加载：

```python
def _load_persisted_conversation_settings(data):
    return ConversationSettings.from_persisted(data or {})
```

与上下文管理相关的配置：
- `max_iterations`: 最大迭代次数（上下文增长上限）
- `confirmation_mode`: 确认模式
- `security_analyzer`: 安全分析器
- `agent_settings`: 包含 LLM/Condenser/MCP/Tools 配置

---

## 三、上下文管理数据流

### 3.1 对话启动时的上下文构建

```
用户发起对话请求
      │
      ▼
LiveStatusAppConversationService._build_start_conversation_request_for_user()
      │
      ├── 1. 获取用户信息 (UserContext.get_user_info)
      │
      ├── 2. 设置 Secrets (Git Provider Token + DB Secrets + API Secrets)
      │      └── _setup_secrets_for_git_providers() → LookupSecret / StaticSecret
      │
      ├── 3. 配置 LLM + MCP
      │      └── _configure_llm_and_mcp() → LLM实例 + mcp_config
      │
      ├── 4. 构建系统消息后缀
      │      └── Planning指令 + WEB_HOST上下文 + 用户自定义suffix
      │
      ├── 5. 选择工具集
      │      └── DEFAULT: get_default_tools() / PLAN: get_planning_tools()
      │
      ├── 6. 构建 AgentContext
      │      └── AgentContext(system_message_suffix, secrets)
      │
      ├── 7. 创建 Agent (AgentSettings.create_agent())
      │
      ├── 8. 应用服务端覆盖 (_apply_server_agent_overrides)
      │      ├── system_prompt_filename + kwargs
      │      ├── LLM tracing metadata
      │      └── Condenser LLM tracing metadata
      │
      ├── 9. 加载 Skills + Hooks
      │      ├── load_and_merge_all_skills() → 更新 agent_context.skills
      │      └── load_hooks_from_agent_server()
      │
      └── 10. 构建 StartConversationRequest
             └── conv_settings.create_request(agent=agent)
```

### 3.2 Agent 运行时的上下文管理循环

```
Agent Step Loop:
      │
      ▼
Stage 1: 组装提示词
  ├── 系统提示 (Jinja2模板: system_prompt.j2 / system_prompt_planning.j2)
  ├── Skills 内容注入
  └── 工具描述注入
      │
      ▼
Stage 2: 调用 LLM
  ├── 获取事件历史 → event_store.get_events()
  ├── 上下文压缩 → condenser.condense(events)
  │   ├── 未超阈值 → 直接返回
  │   └── 超过阈值 → LLM摘要 + 保留最近窗口
  ├── 转换为消息格式 → _events_to_messages(compressed, system_prompt)
  └── LLM.completion_with_tools(messages, tools)
      │
      ▼ [异常恢复]
  ├── FunctionCallValidation → 反馈给LLM重试
  ├── MalformedHistory → RecentCondenser(max=20) 强制压缩
  └── ContextLengthExceeded → RecentCondenser(max=5) 极端降级
      │
      ▼
Stage 3-5: 解析响应 → 安全检查 → 执行工具
  └── 新 Event 加入事件存储 → 上下文增长
```

### 3.3 上下文指标追踪

```
Agent 运行
      │
      ▼
ConversationStateUpdateEvent (key="stats")
      │
      ├── TokenUsage
      │   ├── context_window: 模型上下文窗口大小
      │   ├── per_turn_token: 当前轮次token数
      │   ├── prompt_tokens / completion_tokens
      │   └── cache_read_tokens / cache_write_tokens / reasoning_tokens
      │
      ▼
AppConversationInfoService.process_stats_event()
      │
      ▼
StoredConversationMetadata (SQL更新)
  ├── context_window
  ├── per_turn_token
  ├── accumulated_cost
  └── 各类 token 计数
      │
      ▼
前端 ContextWindowSection 组件
  └── 进度条: per_turn_token / context_window (%)
```

---

## 四、上下文管理的外部依赖与中间件

### 4.1 核心外部依赖: `openhands-sdk`

**版本**: `openhands-sdk==1.21.1`（定义在 [`pyproject.toml:59`](pyproject.toml:59)）

这是上下文管理最核心的外部依赖，提供了以下关键组件：

| SDK 组件 | 用途 |
|----------|------|
| `Agent` | Agent 基类，包含 condenser、agent_context 等字段 |
| `AgentContext` | 上下文容器（skills, secrets, system_message_suffix） |
| `LLMSummarizingCondenser` | LLM 驱动的上下文压缩器 |
| `LLM` | LLM 封装（基于 litellm） |
| `Event` | 事件基类和所有事件类型 |
| `ConversationSettings` | 对话配置 |
| `AgentSettings` / `ACPAgentSettings` | Agent 配置 |
| `Skill` | 技能定义 |
| `LocalWorkspace` | 工作区抽象 |
| `SecretSource` / `LookupSecret` / `StaticSecret` | Secret 抽象 |
| `ConversationStateUpdateEvent` | 对话状态更新事件 |
| `ConversationStats` / `MetricsSnapshot` / `TokenUsage` | 指标数据 |

**关键点**: 上下文管理的核心逻辑（Condenser 的压缩算法、Event 的类型体系、Agent 的 step 循环）全部封装在 SDK 中，App Server 层仅负责**配置构建、参数注入和指标追踪**。

### 4.2 LLM 调用层: `litellm`

Condenser 的摘要生成和 Agent 的主推理都通过 LLM 层调用，底层依赖 `litellm` 库实现多模型适配。Condenser 使用独立的 LLM 实例，通过 `usage_id` 字段区分追踪。

### 4.3 事件持久化中间件

| 实现 | 存储后端 | 适用场景 |
|------|---------|---------|
| `FilesystemEventService` | 本地文件系统 | 开发/本地部署 |
| `AwsEventService` | AWS S3 | 云端部署 |
| `GoogleCloudEventService` | Google Cloud Storage | GCP 部署 (Enterprise) |

事件持久化层直接影响上下文管理——Event 是上下文的基本单元，Event 的读写性能影响 Agent 每轮 step 获取历史上下文的速度。

### 4.4 数据库: SQLAlchemy (异步)

对话元数据（包括 context_window、token 统计等）通过 SQLAlchemy 异步 Session 持久化到关系型数据库。`StoredConversationMetadata` 表记录了上下文窗口指标。

### 4.5 MCP (Model Context Protocol): `fastmcp`

MCP 是 Agent 获取外部工具和上下文的标准协议。在 [`_configure_llm_and_mcp()`](openhands/app_server/app_conversation/live_status_app_conversation_service.py:1061) 中：

```python
from fastmcp.mcp_config import MCPConfig
mcp_config = MCPConfig(**mcp_servers)  # 包装为 SDK 期望的格式
```

MCP 服务器配置是 Agent 上下文的一部分——它们定义了 Agent 可以调用的外部工具和数据源。

### 4.6 Docker 沙箱

Agent 的工具执行发生在 Docker 沙箱中，通过 `AsyncRemoteWorkspace` 通信。Skills 的加载、Setup 脚本执行都依赖沙箱环境。

### 4.7 Jinja2 模板引擎

系统提示词通过 Jinja2 模板渲染：
- `system_prompt.j2` — 默认 Agent 系统提示
- `system_prompt_planning.j2` — Planning Agent 系统提示

模板变量包括：工具信息、Skills、工作目录等上下文内容。

### 4.8 Redis

`redis>=5.2,<7` 被列入项目依赖，主要用于：
- 速率限制 (Rate Limiting)
- 会话状态缓存
- **不用于**上下文管理或记忆存储

---

## 四-B、关于 RAG 和记忆中间件的分析

### 结论：OpenHands 当前**未使用**传统 RAG 或独立记忆中间件

经过对项目源码、依赖配置（`pyproject.toml`）和所有模块的全面搜索，确认以下事实：

#### 1. 无向量数据库 / RAG 检索

项目中**不存在**以下任何 RAG 相关组件或依赖：
- ❌ 向量数据库：ChromaDB、FAISS、Pinecone、Weaviate、Qdrant、Milvus
- ❌ RAG 框架：LangChain Retrieval、LlamaIndex
- ❌ Embedding 检索：无 embedding 向量化和相似度搜索逻辑
- ❌ 知识库检索：无 KnowledgeBase 类或 RAG pipeline

**OpenHands 的"知识检索"替代方案**是 **Skills + Microagents**（见下文），这是一种基于**关键词触发**的轻量级知识注入机制，而非语义检索。

#### 2. 无独立记忆中间件

项目中**不存在**以下记忆相关组件或依赖：
- ❌ Mem0 / MemGPT / Letta 等记忆框架
- ❌ 长期记忆存储（Long-term Memory Store）
- ❌ 工作记忆管理（Working Memory Manager）
- ❌ 跨对话记忆共享机制

**OpenHands 的"记忆"替代方案**是 **Condenser + Event Store + repo.md**（见下文）。

#### 3. OpenHands 的知识管理替代方案：Skills + Microagents

OpenHands 采用了一种**声明式知识注入**而非检索式(RAG)的方案：

```
知识来源 (4层)                    注入方式
─────────────────────────────────────────────
Public Skills (OpenHands/skills)  ──→  AgentContext.skills
User Skills   (~/.openhands/microagents/) ──→  AgentContext.skills
Org Skills    (org/.openhands)    ──→  AgentContext.skills
Repo Skills   (repo/.agents/skills/) ──→  AgentContext.skills
```

**工作原理**：
- Skills 是 Markdown 文件，包含 `name`、`type`、`triggers`（关键词触发器）等 frontmatter
- 当用户消息匹配触发关键词时，Skill 内容被注入到 Agent 的上下文中
- 这是一种**静态知识注入**，不涉及向量检索或语义匹配
- `agent_memory` Skill（[`skills/agent_memory.md`](skills/agent_memory.md)）通过 `.openhands/microagents/repo.md` 文件实现跨对话的"记忆"，本质是**文件持久化**而非记忆中间件

**与 RAG 的对比**：

| 维度 | RAG 方案 | OpenHands Skills 方案 |
|------|---------|----------------------|
| 检索方式 | 语义相似度（Embedding + 向量搜索） | 关键词触发（KeywordTrigger） |
| 知识粒度 | Chunk（文本片段） | 整个 Skill 文件 |
| 动态性 | 运行时实时检索 | 启动时加载，运行时触发 |
| 上下文占用 | 按相关性动态占用 | 触发后全量注入 |
| 适用场景 | 大规模知识库 | 项目级/组织级配置知识 |

#### 4. OpenHands 的记忆替代方案：Condenser + Event Store + repo.md

| 记忆类型 | 传统方案 | OpenHands 方案 |
|---------|---------|---------------|
| **短期记忆**（当前对话） | Working Memory | Event Store（完整事件序列） |
| **中期记忆**（上下文窗口） | 滑动窗口 / 注意力机制 | Condenser（LLM摘要 + 最近窗口） |
| **长期记忆**（跨对话） | Mem0 / 向量数据库 | repo.md 文件持久化（通过 agent_memory Skill） |

**repo.md 机制**：
- Agent 通过 `agent_memory` Skill 被指示将重要知识写入 `.openhands/microagents/repo.md`
- 下次对话启动时，repo.md 作为 Repo Skill 自动加载到 AgentContext.skills
- 这是一种**文件级、人工确认的长期记忆**，而非自动化记忆管理

#### 5. Tavily 搜索：唯一的"检索"能力

Tavily 是项目中唯一的搜索能力，通过 MCP 代理暴露给 Agent：

```python
# mcp_router.py
proxy_client = Client(
    transport=StreamableHttpTransport(
        url=f'https://mcp.tavily.com/mcp/?tavilyApiKey={tavily_api_key}'
    )
)
mcp_server.mount(namespace='tavily', server=proxy_server)
```

- Tavily 是**互联网搜索**工具，不是 RAG
- API Key 由服务端持有，通过 MCP 代理安全暴露给沙箱
- Agent 可在运行时调用 `tavily_search` 工具获取外部信息

#### 6. 设计哲学总结

OpenHands **有意避免**引入 RAG 和记忆中间件，其设计哲学是：

1. **简洁优于复杂**：Skills 的关键词触发比 RAG 的向量检索更简单、更可预测
2. **文件优于数据库**：repo.md 文件持久化比向量数据库更透明、更可控
3. **摘要优于检索**：Condenser 的 LLM 摘要压缩比 RAG 的外部知识检索更自洽
4. **MCP 优于定制**：通过 MCP 协议接入外部工具（如 Tavily），而非自建检索管道

这种设计在**代码助手场景**下是合理的——项目知识通常规模有限（几个 Skill 文件），关键词触发足够覆盖；而 RAG 更适合大规模文档知识库场景。

---

## 五、关键设计模式总结

### 5.1 策略模式 (Condenser)

CondenserBase 作为抽象策略，LLMSummarizingCondenser / RecentCondenser / NoopCondenser 是具体策略。Agent 在运行时通过 Condenser 实例切换压缩策略。

### 5.2 观察者模式 (Event + Callback)

Event 机制实现了解耦——Agent 的每个动作产生 Event，Event 通过 EventService 持久化，同时触发 EventCallback 处理器链。`ConversationStateUpdateEvent` 将上下文指标推送到前端和数据库。

### 5.3 构建者模式 (Agent 构建)

Agent 的构建过程分散在多个方法中（LLM 配置 → MCP 配置 → AgentContext 构建 → Skills 加载 → 服务端覆盖），最终通过 `model_copy()` 不可变更新模式逐步组装。

### 5.4 容错降级策略

上下文溢出时的三层降级：
1. LLM 重试（无效函数调用）
2. Condenser 强制压缩（max=20）
3. 极端降级（max=5，最小上下文窗口）

### 5.5 关注点分离

| 层次 | 关注点 |
|------|--------|
| SDK | 上下文压缩算法、Event 类型定义、Agent step 循环 |
| App Server | 配置构建、参数注入、指标追踪、权限控制 |
| 前端 | 上下文窗口使用率可视化、压缩事件展示 |
| 持久化 | Event 存储、元数据 SQL 记录 |

---

## 六、上下文管理的关键数据流示意

```
                    ┌──────────────┐
                    │   用户消息    │
                    └──────┬───────┘
                           │
                    ┌──────▼───────┐
                    │  Event Store │ ← 对话历史(事件序列)
                    └──────┬───────┘
                           │ get_events()
                    ┌──────▼───────────┐
                    │    Condenser     │
                    │  .condense()     │ ← 上下文压缩
                    └──────┬──────────┘
                           │ 压缩后的事件列表
                    ┌──────▼──────────┐
                    │  to_messages()  │ ← 转为 LLM 消息格式
                    └──────┬─────────┘
                           │
                    ┌──────▼──────────┐
                    │  System Prompt  │ ← Jinja2模板 + Skills + Tools
                    └──────┬──────────┘
                           │
                    ┌──────▼──────────┐
                    │   LLM 调用     │ ← litellm 多模型适配
                    └──────┬──────────┘
                           │
                ┌──────────┼──────────┐
                │          │          │
         ┌──────▼──┐ ┌────▼────┐ ┌──▼────────┐
         │ Action  │ │ Message │ │ Tool Call │
         └──────┬──┘ └────┬────┘ └──┬────────┘
                │          │         │
                └──────────┼─────────┘
                           │
                    ┌──────▼───────┐
                    │  New Events  │ ← 新事件加入 Event Store
                    └──────────────┘
```

---

## 七、核心文件索引

| 文件 | 核心职责 |
|------|---------|
| [`app_conversation_service_base.py`](openhands/app_server/app_conversation/app_conversation_service_base.py) | Condenser 构建、Skills 合并、AgentContext 构建 |
| [`live_status_app_conversation_service.py`](openhands/app_server/app_conversation/live_status_app_conversation_service.py) | 完整的对话启动上下文构建流程、LLM/MCP 配置 |
| [`settings_models.py`](openhands/app_server/settings/settings_models.py) | Settings 模型（包含 agent_settings/conversation_settings） |
| [`event_service.py`](openhands/app_server/event/event_service.py) | Event 服务抽象 |
| [`filesystem_event_service.py`](openhands/app_server/event/filesystem_event_service.py) | 文件系统 Event 持久化 |
| [`aws_event_service.py`](openhands/app_server/event/aws_event_service.py) | AWS S3 Event 持久化 |
| [`sql_app_conversation_info_service.py`](openhands/app_server/app_conversation/sql_app_conversation_info_service.py) | 对话元数据 SQL 持久化（含 context_window 统计） |
| [`user_context.py`](openhands/app_server/user/user_context.py) | 用户上下文抽象（Secrets/Token/Git 信息） |
| [`llm_metadata.py`](openhands/app_server/utils/llm_metadata.py) | LLM 追踪元数据（含 condenser 类型标记） |
| [`condensation-event.ts`](frontend/src/types/v1/core/events/condensation-event.ts) | 前端 Condensation 事件类型定义 |
| [`conversation-state-event.ts`](frontend/src/types/v1/core/events/conversation-state-event.ts) | 前端对话状态事件（含 TokenUsage/context_window） |
| [`context-window-section.tsx`](frontend/src/components/features/conversation/metrics-modal/context-window-section.tsx) | 前端上下文窗口使用率展示 |
