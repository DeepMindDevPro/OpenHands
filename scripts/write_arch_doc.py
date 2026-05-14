#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
target = os.path.expanduser("~/Documents/ai-code/tool_use_coll/openhands_architecture_analysis.md")
os.makedirs(os.path.dirname(target), exist_ok=True)

content = r"""# OpenHands 工程架构深度分析报告

## 1. 工程概览

OpenHands 是一个 AI 软件工程代理平台，核心理念是"Code Less, Make More"。项目采用 Python 后端 + React 前端的全栈架构，通过 LLM 驱动的 Agent 自主完成软件工程任务。

### 1.1 核心源码规模

| 模块 | 代码行数 | 说明 |
|------|----------|------|
| openhands-sdk | 42,652 | Agent/Conversation/LLM/Tool/Security 核心 |
| openhands-tools | 15,055 | 终端/文件编辑/浏览器/搜索等工具 |
| openhands-agent-server | ~8,000 | Agent 运行时服务（外部包） |
| App Server | 29,385 | FastAPI Web 服务层 |
| Enterprise | 105,476 | 商业扩展（含测试59,054行） |
| Frontend | 59,871 | React/TypeScript 前端 |
| **合计** | **~260,000** | 不含 Enterprise 测试约 **200,000** 行 |

### 1.2 SDK 子模块代码规模

| 子模块 | 行数 | 说明 |
|--------|------|------|
| LLM | 7,913 | 大模型集成/流式/重试/路由 |
| Conversation | 6,130 | 对话管理/状态/事件/持久化 |
| Agent | 4,468 | Agent 核心循环/并行执行/Critic |
| Skills | 2,381 | 技能加载/触发/执行 |
| Context | 2,047 | 上下文管理/Condenser/View |
| Tool | 1,707 | 工具定义/注册/Schema |
| Security | 1,702 | 安全分析/确认策略/防御纵深 |
| Plugin | 1,535 | 插件加载/管理 |
| Event | 1,388 | 事件系统 |
| MCP | 665 | MCP 协议集成 |
| 其他(Utils/IO/Workspace/...) | ~13,000 | 工具函数/IO/工作空间等 |

---

## 2. 总体架构设计

### 2.1 分层架构

```
┌─────────────────────────────────────────────────────┐
│                   Frontend (React)                    │
│          WebSocket + REST API + SSE 通信              │
└────────────────────┬────────────────────────────────┘
                     │ HTTP/WS
┌────────────────────▼────────────────────────────────┐
│              App Server (FastAPI)                     │
│  ┌──────────┐ ┌──────────┐ ┌──────────────────────┐ │
│  │ 对话管理  │ │ 事件服务  │ │ 沙箱管理             │ │
│  │Conv.Svc  │ │Event Svc │ │ Sandbox Service      │ │
│  └────┬─────┘ └────┬─────┘ └──────────┬───────────┘ │
│  ┌────▼──────────────▼────────────────▼───────────┐ │
│  │         依赖注入 / 配置 / 中间件                │ │
│  └────────────────────┬───────────────────────────┘ │
└───────────────────────┼─────────────────────────────┘
                        │
┌───────────────────────▼─────────────────────────────┐
│              Agent Server (运行时)                     │
│  ┌────────────────────────────────────────────────┐  │
│  │           LocalConversation                    │  │
│  │  ┌────────┐ ┌──────────┐ ┌──────────────────┐ │  │
│  │  │ Agent  │ │ ConvState│ │ EventStore       │ │  │
│  │  │ (循环) │ │ (状态)   │ │ (事件日志)       │ │  │
│  │  └───┬────┘ └──────────┘ └──────────────────┘ │  │
│  │      │                                        │  │
│  │  ┌───▼────────────────────────────────────┐   │  │
│  │  │           LLM (litellm)                │   │  │
│  │  └───┬────────────────────────────────────┘   │  │
│  │      │                                        │  │
│  │  ┌───▼────────────────────────────────────┐   │  │
│  │  │  ToolDefinition → ToolExecutor         │   │  │
│  │  │  (Terminal/FileEditor/Browser/...)     │   │  │
│  │  └────────────────────────────────────────┘   │  │
│  └────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────┘
                        │
┌───────────────────────▼─────────────────────────────┐
│              Sandbox (Docker/K8s/Remote)              │
│           代码执行 / 文件操作 / 浏览器运行             │
└─────────────────────────────────────────────────────┘
```

### 2.2 包依赖关系

```
openhands-ai (主包)
├── openhands-sdk (核心SDK)
│   ├── Agent / Conversation / LLM / Tool
│   ├── Security / Context / Event / MCP
│   └── Plugin / Skills / Workspace / IO
├── openhands-tools (工具实现)
│   ├── Terminal / FileEditor / Browser
│   ├── Glob / Grep / TaskTracker
│   ├── TaskToolSet / Delegate
│   └── Gemini风格工具 / Planning / TomConsult
├── openhands-agent-server (运行时服务)
│   └── Agent 进程管理 / ACP协议
├── openhands-aci (Agent-Computer Interface)
└── openhands (namespace package)
    └── app_server (Web服务层)
```

**关键设计**：`openhands` 是 namespace package（通过 `pkgutil.extend_path`），允许 `openhands-sdk`、`openhands-tools`、`openhands-agent-server` 三个独立包共享 `openhands` 顶层命名空间。

---

## 3. 核心模块详解

### 3.1 Agent 模块 (4,468行)

**核心类**：`Agent(AgentBase)` 位于 `openhands.sdk.agent.agent`

Agent 是无状态（frozen Pydantic model）的执行引擎，核心循环：

```
1. _initialize(): 初始化工具、MCP、系统提示
2. step(state):
   a. 准备 LLM 消息 (prepare_llm_messages)
   b. 调用 LLM 获取响应
   c. 分类响应 (classify_response): tool_call / message / finish
   d. 分发处理 (ResponseDispatchMixin)
   e. 对于 tool_call: 构建 ActionEvent -> ParallelToolExecutor.execute_batch
   f. 执行工具 -> 生成 ObservationEvent
   g. 更新 ConversationState
3. 循环直到 FinishAction 或达到 max_iterations
```

**并行执行器**：`ParallelToolExecutor` 支持多工具并发调用：
- 基于 `ResourceLockManager` 实现资源级锁
- 工具通过 `declared_resources()` 声明资源依赖
- 同一文件写操作串行化，不同文件操作可并行

**Critic 机制**：`CriticBase` 支持迭代精化：
- Agent 完成后 Critic 评估质量分数
- 若分数低于阈值，自动重试（最多 max_iterations 次）
- 支持 `finish_and_message` 和 `all_actions` 两种评估模式

### 3.2 Conversation 模块 (6,130行)

**核心类层次**：

```
BaseConversation (ABC)
├── LocalConversation  (本地执行，直接运行Agent)
└── RemoteConversation (远程执行，通过HTTP连接Agent Server)
```

**ConversationState**：管理对话执行状态（7种状态）：
- IDLE → RUNNING → FINISHED/ERROR/STUCK
- RUNNING → PAUSED → WAITING_FOR_CONFIRMATION
- 包含 EventStore、SecretRegistry、ResourceLockManager

**StuckDetector**：检测 Agent 陷入循环的模式：
- 重复 Action-Observation 循环
- 重复 Action-Error 循环
- Agent 独白（无用户输入的重复消息）
- 交替模式检测
- 上下文窗口溢出检测

**EventStore**：事件持久化，支持文件系统存储和回放

### 3.3 LLM 模块 (7,913行)

**核心类**：`LLM(BaseModel)` 位于 `openhands.sdk.llm.llm`

功能特性：
- 基于 **litellm** 统一 100+ LLM 提供商接口
- 支持 **Completion API** 和 **Responses API** 双模式
- 流式输出（Streaming）+ Token 计数
- 自动重试（RetryMixin）+ 降级策略（FallbackStrategy）
- 多模态支持（Vision/Image）
- **LLMRegistry**：多 LLM 配置注册（主模型+Condenser模型+子代理模型）
- **LLMProfileStore**：LLM 配置档案管理
- 认证：API Key / OAuth / OpenAI Subscription Auth

**路由机制**：
- `LLMRouter` → 多模型负载均衡（Random/Multimodal 路由）
- 非 Function Calling 模型自动适配（NonNativeFCMixin）

### 3.4 Context 模块 (2,047行)

**Condenser 体系**（上下文压缩）：

```
CondenserBase (ABC)
├── LLMSummarizingCondenser  (LLM摘要压缩，默认)
├── AmortizedCondenser       (分摊压缩)
└── RecentEventsCondenser    (仅保留最近事件)
```

**View**：Condenser 产出的只读事件视图，支持：
- 事件过滤（按类型、时间窗口）
- Tool Loop Atomicity（工具循环原子性）
- Tool Call Matching（工具调用匹配）

### 3.5 Security 模块 (1,702行)

**多层安全架构**：

```
SecurityAnalyzerBase (ABC)
├── EnsembleSecurityAnalyzer  (组合多个分析器，取最严结果)
├── PatternSecurityAnalyzer   (正则模式匹配)
├── PolicyRailSecurityAnalyzer(策略护栏)
├── LLMSecurityAnalyzer       (LLM判断风险)
└── GraySwanSecurityAnalyzer  (灰天鹅检测)
```

**ConfirmationPolicy**：
- `NeverConfirm`：永不确认（默认）
- `ConfirmRisky`：仅高风险操作确认
- `AlwaysConfirm`：所有操作确认

**安全流程**：LLM 预测 security_risk → SecurityAnalyzer 评估 → ConfirmationPolicy 决定是否需要用户确认

### 3.6 Event 系统 (1,388行)

**事件类型层次**：

```
Event (基类)
├── LLMConvertibleEvent (可转换为LLM消息)
│   ├── SystemPromptEvent
│   ├── MessageEvent
│   ├── ActionEvent (工具调用)
│   ├── ObservationEvent (工具返回)
│   └── AgentErrorEvent
├── CondensationRequest
├── CondensationSummaryEvent
├── PauseEvent
├── TokenEvent
└── HookExecutionEvent
```

### 3.7 App Server (29,385行)

**FastAPI 应用**，核心子模块：

| 子模块 | 行数 | 职责 |
|--------|------|------|
| app_conversation | 6,100 | 对话CRUD/启动/实时状态(86KB巨文件) |
| integrations | 7,862 | GitHub/GitLab/Bitbucket/Azure DevOps/Forgejo 集成 |
| sandbox | 3,249 | Docker/K8s/Remote 沙箱管理 |
| utils | 2,206 | 环境变量/Docker工具 |
| settings | 1,290 | 用户设置管理 |
| event_callback | 1,069 | Webhook/事件回调 |
| app_lifespan | 783 | 应用生命周期/数据库迁移 |
| services | 741 | 依赖注入/DB/JWT/HTTP客户端 |
| event | 632 | 事件存储(FileSystem/S3/GCS) |
| secrets | 644 | 密钥管理 |
| config_api | 442 | LLM模型配置API |
| file_store | 458 | 文件存储(Local/S3/GCS/Memory) |
| mcp | 456 | MCP路由 |
| git | 408 | Git操作 |
| pending_messages | 362 | 待处理消息队列 |

**依赖注入**：使用 Injector 模式，所有服务通过 FastAPI Depends 注入

**沙箱服务**：
- `DockerSandboxService`：本地 Docker 沙箱
- `RemoteSandboxService`：远程沙箱（通过 HTTP API）
- 支持 Sandbox Grouping 策略（按仓库/按对话分组）

### 3.8 Frontend (59,871行)

React + TypeScript + Vite 技术栈：
- **V1 架构**：新版 UI，基于事件流驱动
- **WebSocket**：实时接收 Agent 事件
- **状态管理**：Zustand store
- **UI 组件库**：openhands-ui (Storybook)
- **事件类型**：TypeScript 类型定义与后端 Schema 对应

### 3.9 Enterprise (105,476行)

商业扩展层，Polyform Free Trial License（非开源）：
- **server** (16,108行)：SaaS 服务器配置/中间件/认证
- **storage** (10,998行)：用户/组织/授权存储
- **integrations** (11,726行)：SaaS 版 GitHub/Slack/Jira 集成
- **migrations** (6,300行)：数据库迁移
- **tests** (59,054行)：大量集成测试

**扩展方式**：
1. **堆叠**：Enterprise 中间件叠加在 OSS 中间件之上
2. **覆盖**：通过动态导入覆盖 OSS 实现（如 SaasServerConfig 覆盖 ServerConfig）

---

## 4. 亮点设计

### 4.1 Action-Observation 统一协议

所有工具交互通过 Action→Observation 模式统一，LLM 只需理解一种交互协议。结合 DiscriminatedUnionMixin 实现 `kind` 字段自动多态序列化/反序列化，使得新增工具零成本接入事件系统。

### 4.2 工具并行执行与资源声明

`ParallelToolExecutor` + `DeclaredResources` 是精巧的设计：
- 工具声明资源依赖（如 `file:/path`），框架自动加锁
- 不同资源的工具可安全并行，相同资源串行化
- `declared=False`（默认）时保守序列化，`declared=True, keys=()` 时完全并行
- 避免了粗粒度全局锁，也避免了细粒度手动锁管理的复杂性

### 4.3 多层安全防御

安全体系设计为纵深防御（Defense in Depth）：
1. LLM 层：预测 `security_risk` 字段
2. Pattern 层：正则匹配已知危险模式
3. Policy Rail 层：策略组合检测
4. Ensemble 层：取最严结果，fail-closed
5. Confirmation 层：用户确认闸门

### 4.4 上下文压缩（Condenser）

LLM 上下文窗口有限，Condenser 体系优雅解决：
- `LLMSummarizingCondenser`：超出 max_size 时 LLM 生成摘要替换旧事件
- `AmortizedCondenser`：分摊压缩成本
- View 概念：只读事件视图，支持过滤和匹配

### 4.5 Namespace Package 架构

`openhands` 作为 namespace package，允许 SDK/Tools/Agent-Server 三个独立 PyPI 包共享命名空间，实现了核心与实现的解耦，支持独立版本管理和发布。

### 4.6 Critic 迭代精化

Critic 机制允许自动质量评估和迭代改进：Agent 完成任务后 Critic 打分，低于阈值自动重试并提供改进建议，形成闭环反馈。

### 4.7 MCP 协议集成

通过 `MCPToolDefinition` 动态适配外部 MCP 工具，运行时从 JSON Schema 动态创建 Pydantic 模型，实现了与外部工具生态的无缝集成。

### 4.8 StuckDetector 循环检测

5 种循环模式检测（重复动作、重复错误、独白、交替模式、上下文溢出），防止 Agent 陷入无限循环浪费 Token。

### 4.9 远程/本地对话双模式

`LocalConversation` 和 `RemoteConversation` 统一接口，支持：
- 本地开发：直接运行 Agent
- 云端部署：通过 HTTP API 连接远程 Agent Server
- 同一套 Agent/Tool 代码无需修改

---

## 5. 缺陷与改进空间

### 5.1 巨文件问题

`live_status_app_conversation_service.py` 单文件 **86.4KB**（约2,200行），承担了对话创建、启动、消息发送、WebSocket 推送等大量职责，严重违反单一职责原则。应拆分为：
- ConversationCreateService
- ConversationRunService
- ConversationEventService
- ConversationStatusService

### 5.2 Enterprise 与 OSS 耦合

Enterprise 通过动态导入覆盖 OSS 实现，如 `SaasServerConfig` 覆盖 `ServerConfig`。这种方式：
- 脆弱：OSS 重构会破坏 Enterprise
- 难测试：覆盖行为难以单元测试
- 隐式依赖：通过字符串引用，无编译时检查

**改进**：应使用显式插件机制或策略模式替代动态导入。

### 5.3 配置管理复杂度

`config.py` (21.4KB) 集中管理所有服务注入，随着功能增长已成为瓶颈。依赖注入配置与业务逻辑混合，可读性差。

**改进**：采用模块化注入，每个子模块自注册依赖。

### 5.4 Agent 无状态设计的权衡

Agent 设计为 frozen Pydantic model（不可变），理论上利于序列化和恢复。但实际：
- `_state` 等私有属性通过 PrivateAttr 绕过不可变约束
- 运行时状态管理分散在 ConversationState、EventStore 等多处
- Agent "无状态" 名不副实

**改进**：明确 Agent 的状态边界，或坦诚接受有状态设计。

### 5.5 事件系统缺乏类型安全

Event 体系使用 DiscriminatedUnionMixin 的 `kind` 字段做分发，但：
- 前后端事件类型定义手动维护（TypeScript vs Python），容易不一致
- 大量 isinstance 检查和类型窄化代码
- 缺乏从后端 Schema 自动生成前端类型的机制

**改进**：从 Pydantic Schema 自动生成 TypeScript 类型定义。

### 5.6 测试覆盖率不均

- Enterprise 有 59,054 行测试（占自身 56%）
- App Server 测试较少（29,385 行实现，测试比例偏低）
- SDK 核心模块测试未包含在此仓库中

### 5.7 同步/异步混用

LLM 模块中 litellm 同时支持同步和异步调用，但：
- `MCPToolExecutor` 使用 `call_async_from_sync` 桥接
- 部分 ToolExecutor 是同步的，被 ParallelToolExecutor 放入线程池
- 异步边界处理不一致，可能导致事件循环阻塞

**改进**：统一为异步接口，或明确标注同步/异步边界。

### 5.8 过度抽象风险

- DiscriminatedUnionMixin 被广泛用于所有数据模型，增加了序列化/反序列化复杂度
- 某些只有一个实现的抽象基类（如 SandboxService 只有 Docker 和 Remote 两个实现）过度抽象
- Condenser 体系有多个实现但默认只用 LLMSummarizingCondenser

### 5.9 日志与可观测性

- 日志混用 `logging.getLogger` 和 `get_logger`（SDK 自定义）
- OpenTelemetry 集成仅部分模块
- Laminar 可观测性是可选的，缺乏统一的 tracing 标准

---

## 6. 架构演进趋势

1. **SDK 独立化**：核心逻辑已从 monolith 拆分为 openhands-sdk / openhands-tools / openhands-agent-server 三个独立包
2. **MCP 优先**：MCP 协议正在成为工具集成的首选方式，内部工具也适配了 MCP Schema
3. **多 Agent 协作**：TaskToolSet/DelegateTool 支持子代理，朝多 Agent 编排演进
4. **V1 API 迁移**：前端正从 V0 迁移到 V1 架构（事件驱动 vs 旧版状态驱动）
5. **容器化运行时**：从 Docker 沙箱扩展到 K8s/Remote 沙箱，支持更大规模部署
6. **ACP 协议**：Agent-Client Protocol 支持标准化的 Agent 间通信

---

## 7. 总结

OpenHands 是一个设计精良的 AI Agent 平台，核心亮点在于：

- **统一的 Action-Observation 协议**使工具扩展极其简洁
- **并行执行+资源声明**机制在安全性和性能间取得平衡
- **多层安全防御**体系体现了对 AI Agent 安全性的深刻理解
- **Namespace Package** 架构实现了核心与实现的优雅解耦
- **Condenser 上下文压缩**解决了长对话的 Token 限制问题

主要改进空间在于：

- 巨文件拆分和模块化（特别是 `live_status_app_conversation_service.py`）
- Enterprise 与 OSS 的耦合机制需重构
- 同步/异步接口统一
- 前后端类型定义自动同步
- 测试覆盖率均衡化

整体而言，OpenHands 在 AI Agent 工程化方面处于行业前沿，其工具系统、安全体系、上下文管理等设计值得深入学习和借鉴。
"""

with open(target, "w", encoding="utf-8") as f:
    f.write(content)
print(f"Written {os.path.getsize(target)} bytes to {target}")
