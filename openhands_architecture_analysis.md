# OpenHands 工程架构深度分析报告

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

**核心类**：`Agent(CriticMixin, ResponseDispatchMixin, AgentBase)` 位于 `openhands.sdk.agent.agent`

Agent 是无状态（frozen Pydantic model）的执行引擎，核心循环：

```
1. init_state(): 初始化系统提示(SystemPromptEvent)、工具列表、动态上下文(secrets+agent_context)
2. step(conversation):
   a. 检查 pending_actions（确认模式下的隐式确认，直接执行并返回）
   b. 检查 Hook 阻塞消息（UserPromptSubmit hook 阻止的消息，标记FINISHED）
   c. 准备 LLM 消息 (prepare_llm_messages + condenser)
   d. 若 condenser 返回 Condensation 事件，触发压缩并返回
   e. 调用 LLM (make_llm_completion) 获取响应
   f. 异常处理链：
      - FunctionCallValidationError → 反馈给LLM继续
      - LLMMalformedConversationHistoryError → 触发Condensation恢复
      - LLMContextWindowExceedError → 触发Condensation压缩
   g. 分类响应 (classify_response):
      - TOOL_CALLS → _handle_tool_calls → ActionEvent
      - CONTENT → _handle_content_response → MessageEvent + FinishAction
      - REASONING_ONLY / EMPTY → _handle_no_content_response → 继续
   h. _execute_actions → _ActionBatch.prepare → emit → finalize
      - finalize 检查用户确认需求 (_requires_user_confirmation)
      - Critic 迭代精化检查 (_check_iterative_refinement)
3. 循环由 LocalConversation.run() 控制，直到 FINISHED / ERROR / STUCK
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

**ConversationState**：管理对话执行状态（8种状态）：
- IDLE / PAUSED / ERROR / STUCK → RUNNING（run() 启动时自动转换）
- RUNNING → FINISHED（Agent完成或Hook允许停止）
- RUNNING → WAITING_FOR_CONFIRMATION（安全策略要求确认时break）
- FINISHED 时 Hook 可拒绝停止，回退到 RUNNING 继续
- WAITING_FOR_CONFIRMATION → RUNNING（下次run()确认后）
- DELETING（对话删除中）
- 终态：FINISHED / ERROR / STUCK（is_terminal()判断，IDLE不是终态）
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
- 支持 **Completion API** 和 **Responses API** 双模式：
  - Completion API：传统 Chat Completion，支持 native function calling 和 prompt mock 两种策略
  - Responses API：OpenAI 新版接口，Message[] -> (instructions, input[]) 映射，流式使用 SyncResponsesAPIStreamingIterator
  - 两种模式共享重试、遥测、Fallback 机制
- 流式输出（Streaming）+ Token 计数
- 自动重试（RetryMixin）+ 降级策略（FallbackStrategy）
- 非 Function Calling 模型自动适配（prompt mock 策略）
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

**依赖注入**：`AppServerConfig` 集中管理 12 个服务注入器（Injector）：
- LLMModelService / EventService / EventCallbackService / SandboxService
- AppConversationService / AppConversationInfoService / PendingMessageService
- UserContext / JwtService / HttpxClient / DbSession / WebClientConfig
- 每个 Injector 通过 FastAPI Depends 注入，支持运行时替换（Enterprise 覆盖 Injector 实现）
- `config_from_env()` 根据环境变量自动选择实现（如 RUNTIME=remote -> RemoteSandboxService）
- 全局单例 `get_global_config()` + `InjectorState` 管理注入状态

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
1. **Namespace Package 堆叠**：Enterprise 模块与 OSS 模块共享 `openhands` 命名空间，可叠加中间件
2. **get_impl() 动态覆盖**：`import_utils.get_impl()` 根据 `OPENHANDS_CONFIG_CLS` 环境变量动态导入实现类（如 `server.config.SaaSServerConfig`），使用 `importlib.import_module` 加载并验证子类关系
3. **字符串类引用**：ServerConfig 中 `settings_store_class`、`secret_store_class`、`user_auth_class` 等字段通过 `import_from()` 延迟加载，Enterprise 可覆盖这些字段指向自己的实现

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

---

## 8. 遗漏要点补充

> 以下内容为源码深度验证中发现的原报告遗漏核心模块和机制。

### 8.1 Hook 系统（完全遗漏）

Hook 系统是 Agent 执行流程中的关键拦截层，原报告仅在 Agent.step() 中提及"Hook 阻塞消息"，未展开描述。

**HookConfig**：从 `.openhands/hooks.json` 加载，支持：
- `UserPromptSubmit` Hook：在用户消息提交前拦截，可阻止消息发送或修改消息内容
- Hook 可阻断 Agent 执行（step 中检查 Hook 阻塞消息，标记 FINISHED）
- Hook 可拒绝 FINISHED 状态（ConversationState 中 Hook 拒绝时回退到 RUNNING）

**加载流程**：App Server 通过 `fetch_hooks_from_agent_server()` 调用 Agent Server 的 `/api/hooks` 端点，传入 `project_dir` 参数，从工作区的 `.openhands/hooks.json` 加载配置。

### 8.2 对话启动完整组装流程（遗漏）

对话启动是一个涉及 10+ 步骤的复杂组装过程，原报告未描述。核心流程：

```
1. 用户请求 → AppConversationStartRequest
2. 验证/继承父对话配置（sandbox_id, repository, branch, llm_model）
3. 应用 SuggestedTask 默认值（自动生成 initial_message）
4. 等待 Sandbox 启动（STARTING → RUNNING）
5. 运行 setup.sh 脚本（通过 AsyncRemoteWorkspace）
6. 组装 StartConversationRequest：
   a. 配置 Secrets（Git Provider Token → LookupSecret/StaticSecret）
   b. 配置 LLM + MCP（系统MCP + 用户自定义MCP）
   c. 选择工具集（Default Tools vs Planning Tools）
   d. AgentSettings.create_agent() → 应用 Server 覆盖
   e. 加载 Skills（5种来源，见8.3）
   f. 加载 Hooks（见8.1）
   g. 构建 Plugin 参数消息
7. POST /api/conversations 或 /api/acp/conversations
8. 保存 AppConversationInfo + 注册 EventCallback（SetTitleCallbackProcessor）
9. 处理待发送消息（PendingMessageService）
```

### 8.3 Skill 多源加载体系（遗漏展开）

Skills 有 5 种来源，通过 Agent Server 的 `/api/skills` 端点统一加载：

| 来源 | 路径 | 说明 |
|------|------|------|
| Public Skills | OpenHands/skills GitHub 仓库 | 社区共享技能 |
| User Skills | ~/.openhands/skills/ | 用户私有技能 |
| Organization Skills | {org}/.openhands 仓库 | 组织级技能 |
| Project Skills | .agents/skills/ / .openhands/microagents/ | 项目级技能 |
| Sandbox Skills | exposed_urls 配置 | 沙箱环境技能 |

Skills 通过 `KeywordTrigger` 和 `TaskTrigger` 触发，合并时后加载的覆盖先加载的（按名称去重）。

### 8.4 EventCallback / Webhook 系统（完全遗漏）

EventCallback 系统是事件驱动的回调机制，支持外部系统集成：

**核心组件**：
- `EventCallbackProcessor`（ABC + DiscriminatedUnionMixin）：回调处理器基类
- `LoggingCallbackProcessor`：日志记录处理器（示例）
- `SetTitleCallbackProcessor`：自动从 Agent 响应中提取标题
- Enterprise 扩展：`GitHubV1CallbackProcessor` / `SlackV1CallbackProcessor` / `JiraV1CallbackProcessor` / `GitLabV1CallbackProcessor` / `BitbucketV1CallbackProcessor`

**回调流程**：
1. Agent 产生事件 → EventStore 存储
2. EventCallbackService 查询匹配的 Callback（按 conversation_id 过滤）
3. Processor 执行回调 → 返回 EventCallbackResult（SUCCESS/FAILED/RETRY）
4. 支持重试机制和错误分类

**Webhook 路由**：`/api/v1/webhooks/*` 端点，支持：
- 事件过滤（按类型、对话ID）
- JWT 认证 + Session API Key 认证
- 回调结果跟踪和状态监控
- 错误分类（budget_exceeded / model_error / runtime_error / timeout / user_cancelled）

### 8.5 Secret 管理体系（完全遗漏）

Secret 管理支持两种类型，解决不同场景下的密钥注入问题：

| 类型 | 类名 | 用途 |
|------|------|------|
| 静态密钥 | `StaticSecret` | 直接存储密钥值（SecretStr），用于本地/CLI模式 |
| 查找密钥 | `LookupSecret` | 存储 URL + Headers，运行时通过 HTTP 请求获取值 |

**LookupSecret 设计**：Web 模式下，Git Provider Token 不直接暴露给沙箱，而是通过 `LookupSecret` 存储 App Server 的 webhook 端点 URL，沙箱运行时通过 HTTP 请求获取实际 Token。这实现了密钥的安全代理——沙箱永远不直接接触原始 Token。

### 8.6 ACP Agent 双模式（完全遗漏）

系统支持两种 Agent 模式，通过 `AgentSettings` 的 DiscriminatedUnion 区分：

| 模式 | 设置类 | Agent 类 | 路由路径 |
|------|--------|----------|----------|
| OpenHands Agent | `OpenHandsAgentSettings` | `Agent` | `/api/conversations` |
| ACP Agent | `ACPAgentSettings` | `ACPAgent` | `/api/acp/conversations` |

ACP Agent 使用外部 ACP 服务器（如 Claude Code、Codex），通过环境变量注入凭证，模型名通过 `acp_model` 字段指定。ACP 模式不使用 OpenHands 的 LLM/Condenser/Security 体系，而是完全委托给外部 Agent 进程。

### 8.7 Planning Agent vs Default Agent（工具集差异未描述）

两种 Agent 类型使用完全不同的工具集：

| 类型 | 系统提示模板 | 工具集 |
|------|-------------|--------|
| Default Agent | `system_prompt.j2` | `get_default_tools()`：Terminal / FileEditor / Browser / Glob / Grep / TaskTracker / SubAgents |
| Planning Agent | `system_prompt_planning.j2` | `get_planning_tools()`：仅文件规划工具（PlanFileEditor 等） |

Planning Agent 的指令明确声明"**仅负责规划，不负责实现**"，Plan 文件存储在 `.agents_tmp/PLAN.md`（或 `agents-tmp-config/PLAN.md` for GitLab/Azure DevOps）。

### 8.8 Suggested Task / Resolver 系统（完全遗漏）

**SuggestedTask**：从 Git Provider 自动发现可操作任务：

| 任务类型 | 说明 |
|----------|------|
| MERGE_CONFLICTS | 合并冲突待解决 |
| FAILING_CHECKS | CI/CD 检查失败 |
| UNRESOLVED_COMMENTS | PR 未解决的评论 |
| OPEN_ISSUE | 开放的 Issue |
| OPEN_PR | 开放的 PR |

每个 Git Provider（GitHub/GitLab/Bitbucket/Azure DevOps/Forgejo）通过 `*ResolverMixin` 实现任务发现，使用 Jinja2 模板生成任务提示。`ConversationTrigger` 枚举记录触发来源（resolver/gui/suggested_task/slack/jira/linear/bitbucket/automation）。

### 8.9 Analytics 遥测体系（完全遗漏）

**AnalyticsService**：基于 PostHog 的服务端遥测：
- **同意门控**：`consented=False` 时所有调用为 no-op
- **OSS/SaaS 双模式**：OSS 模式设置 `$process_person_profile=False`，SaaS 模式支持 `set_person_properties` 和 `group_identify`
- **Feature Env 前缀**：staging/feature 环境的 distinct_id 添加 `FEATURE_` 前缀
- **SDK 错误隔离**：所有异常被捕获并记录，永不向上抛出
- **通用属性**：`app_mode` + `is_feature_env` 自动附加到每个事件

### 8.10 Sandbox Grouping 策略（完全遗漏）

Sandbox Grouping 决定多个对话如何共享沙箱：

| 策略 | 说明 |
|------|------|
| NO_GROUPING | 每个对话独立沙箱（默认） |
| GROUP_BY_NEWEST | 加入最新创建的沙箱 |
| LEAST_RECENTLY_USED | 加入最久未使用的沙箱 |
| FEWEST_CONVERSATIONS | 加入对话数最少的沙箱 |
| ADD_TO_ANY | 加入任意可用沙箱 |

非 NO_GROUPING 策略下，working_dir 会附加 `/{conversation_id.hex}` 子目录实现隔离。

### 8.11 LLM Profiles 配置管理（完全遗漏）

`LLMProfiles` 支持用户保存和切换多套 LLM 配置：
- 保存当前 `AgentSettings.llm` 配置为命名 Profile
- 在 Profile 间快速切换
- Profile 数量有上限
- 切换 Profile 时自动更新 `active` 指针
- 如果用户直接修改 `agent_settings.llm`（非 Profile 切换），`reconcile_active_profile()` 会清除不匹配的 active 标记

### 8.12 前端 V1 事件流架构（描述不足）

V1 前端架构核心：

```
WebSocket (Agent Server) → ConversationWebSocketProvider
  → 解析事件 → useEventStore (Zustand)
    → 事件去重 (eventIds Set)
    → 时间排序 (ISO timestamp 比较)
    → 事件分发：
      - ActionEvent → useBrowserStore / useCommandStore
      - ConversationStateUpdateEvent → useV1ConversationStateStore
      - MessageEvent → useErrorMessageStore / useOptimisticUserMessageStore
      - StatsEvent → useMetricsStore
      - ActionEvent cache invalidation → React Query invalidation
```

前端同时支持 V0（旧版状态驱动）和 V1（事件驱动）事件，通过 `isV1Event` 类型守卫区分。

### 8.13 Plugin 系统（展开不足）

Plugin 系统允许在对话启动时加载外部代码：
- `PluginSpec` 继承 SDK 的 `PluginSource`，增加 `parameters` 字段
- Plugin 参数被格式化并追加到 `initial_message` 中（而非系统提示），Agent 通过用户消息感知插件配置
- 多个 Plugin 的参数按 Plugin 名称分组展示

---

## 9. 核心链路调用流程图

### 9.1 Agent 循环执行完整流程

```
┌─────────────────────────────────────────────────────────────┐
│                    LocalConversation.run()                    │
│                                                               │
│  ┌──────────┐                                                 │
│  │ IDLE/    │                                                 │
│  │ PAUSED   │──→ RUNNING                                      │
│  └──────────┘        │                                        │
│                      ▼                                        │
│              ┌───────────────┐                                │
│              │  Agent.step() │◄──────────┐                    │
│              └───────┬───────┘           │                    │
│                      │                   │                    │
│    ┌─────────────────┼─────────────────┐ │                    │
│    │ 1. 检查 pending_actions           │ │                    │
│    │    → 隐式确认，直接执行返回       │ │                    │
│    ├─────────────────┼─────────────────┤ │                    │
│    │ 2. 检查 Hook 阻塞消息            │ │                    │
│    │    → UserPromptSubmit Hook 阻止   │ │                    │
│    │    → 标记 FINISHED               │ │                    │
│    ├─────────────────┼─────────────────┤ │                    │
│    │ 3. 准备 LLM 消息                 │ │                    │
│    │    prepare_llm_messages()         │ │                    │
│    │         │                         │ │                    │
│    │         ▼                         │ │                    │
│    │    Condenser.condense()           │ │                    │
│    │    ├─ 返回 View → 继续LLM调用    │ │                    │
│    │    └─ 返回 Condensation → 压缩    │ │                    │
│    │       触发压缩并返回              │ │                    │
│    ├─────────────────┼─────────────────┤ │                    │
│    │ 4. 调用 LLM                      │ │                    │
│    │    make_llm_completion()          │ │                    │
│    │    ├─ Completion API / Responses  │ │                    │
│    │    ├─ 流式输出 Streaming          │ │                    │
│    │    ├─ 自动重试 RetryMixin         │ │                    │
│    │    └─ 降级 FallbackStrategy       │ │                    │
│    ├─────────────────┼─────────────────┤ │                    │
│    │ 5. 异常处理链                    │ │                    │
│    │    ├─ FunctionCallValidationError │ │                    │
│    │    │  → 反馈给LLM继续            │ │                    │
│    │    ├─ LLMMalformedHistoryError    │ │                    │
│    │    │  → 触发Condensation恢复     │ │                    │
│    │    └─ LLMContextWindowExceedError │ │                    │
│    │       → 触发Condensation压缩     │ │                    │
│    ├─────────────────┼─────────────────┤ │                    │
│    │ 6. 分类响应 classify_response    │ │                    │
│    │    ├─ TOOL_CALLS → _handle_tool   │ │                    │
│    │    │  → ActionEvent               │ │                    │
│    │    ├─ CONTENT → _handle_content   │ │                    │
│    │    │  → MessageEvent+FinishAction │ │                    │
│    │    └─ REASONING_ONLY/EMPTY        │ │                    │
│    │       → _handle_no_content → 继续 │ │                    │
│    ├─────────────────┼─────────────────┤ │                    │
│    │ 7. 执行动作 _execute_actions     │ │                    │
│    │    _ActionBatch.prepare()         │ │                    │
│    │    ├─ emit ActionEvent            │ │                    │
│    │    ├─ SecurityAnalyzer评估        │ │                    │
│    │    │  → ConfirmationPolicy决定    │ │                    │
│    │    ├─ ParallelToolExecutor        │ │                    │
│    │    │  → ResourceLockManager加锁   │ │                    │
│    │    │  → 并发执行(声明资源可并行)  │ │                    │
│    │    └─ emit ObservationEvent       │ │                    │
│    ├─────────────────┼─────────────────┤ │                    │
│    │ 8. Finalize 检查                 │ │                    │
│    │    ├─ _requires_user_confirmation │ │                    │
│    │    │  → WAITING_FOR_CONFIRMATION  │ │                    │
│    │    └─ _check_iterative_refinement │ │                    │
│    │       → Critic 评估质量           │ │                    │
│    │       → 分数低于阈值 → 重试      │ │                    │
│    └─────────────────┴─────────────────┘ │                    │
│                      │                   │                    │
│                      ▼                   │                    │
│              ┌───────────────┐           │                    │
│              │ StuckDetector │           │                    │
│              │ 检测5种循环   │           │                    │
│              ├───────────────┤           │                    │
│              │ Hook 检查     │           │                    │
│              │ 可拒绝FINISHED│           │                    │
│              └───────┬───────┘           │                    │
│                      │                   │                    │
│         ┌────────────┼────────────┐      │                    │
│         │            │            │      │                    │
│    FINISHED      ERROR        STUCK     │                    │
│  (终态)        (终态)       (终态)      │                    │
│         │                                 │                    │
│         └─ Hook拒绝 → RUNNING ──────────┘                    │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

### 9.2 上下文压缩（Condenser）流程

```
┌──────────────────────────────────────────────────────────────┐
│                    Condenser 上下文压缩流程                    │
│                                                              │
│  Agent.step() 准备LLM消息                                    │
│       │                                                      │
│       ▼                                                      │
│  prepare_llm_messages(event_store)                           │
│       │                                                      │
│       ▼                                                      │
│  ┌─────────────────────────────────────────┐                │
│  │        Condenser.condense(events)        │                │
│  │                                          │                │
│  │  ┌────────────────────────────────────┐  │                │
│  │  │ 事件数 > max_size ?                │  │                │
│  │  └──────────┬─────────────────────────┘  │                │
│  │        NO   │   YES                       │                │
│  │        │    │                             │                │
│  │        │    ▼                             │                │
│  │        │  ┌──────────────────────────┐   │                │
│  │        │  │ LLMSummarizingCondenser  │   │                │
│  │        │  │                          │   │                │
│  │        │  │ 1. 分割事件：            │   │                │
│  │        │  │    keep_recent (最近N个) │   │                │
│  │        │  │    to_summarize (旧事件) │   │                │
│  │        │  │                          │   │                │
│  │        │  │ 2. LLM生成摘要：         │   │                │
│  │        │  │    调用 Condenser LLM    │   │                │
│  │        │  │    (独立LLM配置/模型)    │   │                │
│  │        │  │                          │   │                │
│  │        │  │ 3. 输出：                │   │                │
│  │        │  │    CondensationSummary    │   │                │
│  │        │  │    + keep_recent events   │   │                │
│  │        │  └──────────┬───────────────┘   │                │
│  │        │             │                    │                │
│  │        │             ▼                    │                │
│  │        │  返回 Condensation 事件          │                │
│  │        │  (触发压缩，不调用LLM)          │                │
│  │        │                                  │                │
│  │        ▼                                  │                │
│  │  返回 View (只读事件视图)                 │                │
│  │    ├─ 事件过滤（按类型、时间窗口）        │                │
│  │    ├─ Tool Loop Atomicity（原子性）       │                │
│  │    └─ Tool Call Matching（匹配）          │                │
│  └──────────────────────────────────────────┘                │
│       │                                                      │
│       ▼                                                      │
│  转换为 LLM Message[] 格式                                   │
│  (SystemPrompt → CondensationSummary → Messages → ...)       │
│       │                                                      │
│       ▼                                                      │
│  调用 LLM make_llm_completion()                              │
│                                                              │
│  ┌──────────────────────────────────────────┐               │
│  │ 异常触发的压缩路径：                     │               │
│  │                                          │               │
│  │ LLMContextWindowExceedError              │               │
│  │  → 强制压缩（忽略 max_size 检查）       │               │
│  │  → 缩小 keep_recent 窗口                │               │
│  │                                          │               │
│  │ LLMMalformedConversationHistoryError     │               │
│  │  → 恢复性压缩（修复损坏的历史）         │               │
│  └──────────────────────────────────────────┘               │
└──────────────────────────────────────────────────────────────┘
```

### 9.3 任务拆解规划模块（Planning Agent）

```
┌──────────────────────────────────────────────────────────────┐
│              Planning Agent 任务拆解流程                      │
│                                                              │
│  用户请求 (AgentType=PLAN)                                    │
│       │                                                      │
│       ▼                                                      │
│  ┌──────────────────────────────────────┐                   │
│  │ App Server 组装                       │                   │
│  │                                       │                   │
│  │ 1. 选择 Planning 工具集               │                   │
│  │    get_planning_tools(plan_path)      │                   │
│  │    ├─ PlanFileEditor                  │                   │
│  │    └─ (只读查询工具)                  │                   │
│  │                                       │                   │
│  │ 2. 设置系统提示                       │                   │
│  │    system_prompt_planning.j2          │                   │
│  │    + format_plan_structure()          │                   │
│  │                                       │                   │
│  │ 3. 设置 Plan 路径                     │                   │
│  │    .agents_tmp/PLAN.md                │                   │
│  │    (GitLab/AzureDevOps:               │                   │
│  │     agents-tmp-config/PLAN.md)        │                   │
│  └──────────────────┬───────────────────┘                   │
│                      │                                      │
│                      ▼                                      │
│  ┌──────────────────────────────────────┐                   │
│  │ Planning Agent 执行                   │                   │
│  │                                       │                   │
│  │ 系统提示约束：                        │                   │
│  │ "仅负责规划，不负责实现"              │                   │
│  │                                       │                   │
│  │ 1. 分析用户需求                       │                   │
│  │ 2. 生成 PLAN.md 结构                  │                   │
│  │    ├─ Goal: 总体目标                  │                   │
│  │    ├─ Steps:                          │                   │
│  │    │   ├─ Step 1: [任务描述]          │                   │
│  │    │   │   └─ Dependencies: [无]      │                   │
│  │    │   ├─ Step 2: [任务描述]          │                   │
│  │    │   │   └─ Dependencies: [Step 1]  │                   │
│  │    │   └─ ...                         │                   │
│  │    └─ Notes: 注意事项                 │                   │
│  │                                       │                   │
│  │ 3. 使用 PlanFileEditor 写入 PLAN.md   │                   │
│  │ 4. 完成（MessageEvent + FinishAction）│                   │
│  └──────────────────┬───────────────────┘                   │
│                      │                                      │
│                      ▼                                      │
│  ┌──────────────────────────────────────┐                   │
│  │ Code Agent 接续执行                   │                   │
│  │                                       │                   │
│  │ 1. 读取 PLAN.md                       │                   │
│  │ 2. 使用 get_default_tools() 全量工具  │                   │
│  │ 3. 按 Plan 逐步实现                   │                   │
│  │ 4. 更新 Plan 状态标记                 │                   │
│  └──────────────────────────────────────┘                   │
└──────────────────────────────────────────────────────────────┘
```

### 9.4 工具调用完整流程

```
┌──────────────────────────────────────────────────────────────┐
│                    工具调用完整流程                            │
│                                                              │
│  LLM 响应: tool_calls=[{name, arguments}]                    │
│       │                                                      │
│       ▼                                                      │
│  classify_response() → TOOL_CALLS                             │
│       │                                                      │
│       ▼                                                      │
│  _handle_tool_calls() → 创建 ActionEvent                     │
│       │                                                      │
│       ▼                                                      │
│  _ActionBatch.prepare()                                       │
│       │                                                      │
│       ▼                                                      │
│  ┌─────────────────────────────────────────────────┐        │
│  │ SecurityAnalyzer 安全评估                        │        │
│  │                                                  │        │
│  │ LLM 预测 security_risk                           │        │
│  │    │                                             │        │
│  │    ▼                                             │        │
│  │ PatternSecurityAnalyzer (正则匹配)               │        │
│  │    │                                             │        │
│  │    ▼                                             │        │
│  │ PolicyRailSecurityAnalyzer (策略护栏)            │        │
│  │    │                                             │        │
│  │    ▼                                             │        │
│  │ EnsembleSecurityAnalyzer (取最严结果)            │        │
│  │    │                                             │        │
│  │    ▼                                             │        │
│  │ ConfirmationPolicy 决策                          │        │
│  │ ├─ NeverConfirm → 直接执行                      │        │
│  │ ├─ ConfirmRisky → 仅高风险操作需确认            │        │
│  │ └─ AlwaysConfirm → 所有操作需确认               │        │
│  │                                                  │        │
│  │ 需要确认 → WAITING_FOR_CONFIRMATION              │        │
│  │ 不需确认 → 继续执行                              │        │
│  └──────────────────────┬──────────────────────────┘        │
│                          │                                  │
│                          ▼                                  │
│  ┌─────────────────────────────────────────────────┐        │
│  │ ParallelToolExecutor 并行执行                    │        │
│  │                                                  │        │
│  │ 1. 分析工具的资源声明                            │        │
│  │    tool.declared_resources()                     │        │
│  │    ├─ declared=False → 保守序列化               │        │
│  │    ├─ declared=True, keys=() → 完全并行         │        │
│  │    └─ declared=True, keys=["file:/x"] →         │        │
│  │       同一文件串行，不同文件并行                 │        │
│  │                                                  │        │
│  │ 2. ResourceLockManager 加锁                      │        │
│  │    请求资源锁 → 获取 → 执行 → 释放              │        │
│  │                                                  │        │
│  │ 3. 执行工具                                      │        │
│  │    ├─ Terminal: 沙箱内执行命令                   │        │
│  │    ├─ FileEditor: 沙箱内编辑文件                 │        │
│  │    ├─ Browser: Playwright 浏览器操作             │        │
│  │    ├─ Glob/Grep: 文件搜索                       │        │
│  │    ├─ TaskTracker: 任务追踪                      │        │
│  │    ├─ DelegateTool: 子代理委托                   │        │
│  │    └─ MCPToolDefinition: 外部MCP工具             │        │
│  │                                                  │        │
│  │ 4. 产出 ObservationEvent                         │        │
│  │    ├─ 成功 → 工具返回结果                        │        │
│  │    └─ 失败 → AgentErrorEvent                     │        │
│  └──────────────────────┬──────────────────────────┘        │
│                          │                                  │
│                          ▼                                  │
│  ┌─────────────────────────────────────────────────┐        │
│  │ Finalize 后处理                                  │        │
│  │                                                  │        │
│  │ 1. _requires_user_confirmation 检查              │        │
│  │ 2. _check_iterative_refinement (Critic)          │        │
│  │    ├─ CriticBase.evaluate() → 质量分数           │        │
│  │    ├─ 分数 >= 阈值 → 接受结果                   │        │
│  │    └─ 分数 < 阈值 → 自动重试(最多max_iterations) │        │
│  │ 3. 发出事件到 EventStore                         │        │
│  │ 4. 触发 EventCallback 处理链                     │        │
│  └─────────────────────────────────────────────────┘        │
└──────────────────────────────────────────────────────────────┘
```

### 9.5 对话启动完整组装流程

```
┌──────────────────────────────────────────────────────────────┐
│              对话启动完整组装流程                              │
│                                                              │
│  用户请求: AppConversationStartRequest                        │
│       │                                                      │
│       ▼                                                      │
│  ┌─────────────────────────────────────────────────┐        │
│  │ Step 1: 验证与继承                              │        │
│  │ ├─ 继承父对话: sandbox_id/repository/branch/LLM│        │
│  │ └─ 应用 SuggestedTask: 生成 initial_message    │        │
│  └──────────────────────┬──────────────────────────┘        │
│                          │                                  │
│                          ▼                                  │
│  ┌─────────────────────────────────────────────────┐        │
│  │ Step 2: 沙箱启动                                │        │
│  │ ├─ SandboxGroupingStrategy 决定沙箱分配         │        │
│  │ ├─ Docker/Process/Remote 三种模式               │        │
│  │ ├─ 等待 STARTING → RUNNING                      │        │
│  │ └─ 获取 Agent Server URL (exposed_urls)         │        │
│  └──────────────────────┬──────────────────────────┘        │
│                          │                                  │
│                          ▼                                  │
│  ┌─────────────────────────────────────────────────┐        │
│  │ Step 3: Setup 脚本执行                          │        │
│  │ ├─ .openhands/setup.sh (项目级)                 │        │
│  │ ├─ .openhands/pre-commit.sh (Git hooks)         │        │
│  │ └─ 通过 AsyncRemoteWorkspace 执行               │        │
│  └──────────────────────┬──────────────────────────┘        │
│                          │                                  │
│                          ▼                                  │
│  ┌─────────────────────────────────────────────────┐        │
│  │ Step 4: 组装对话配置                            │        │
│  │                                                  │        │
│  │ 4a. Secrets 配置                                │        │
│  │     ├─ Git Provider Token → LookupSecret(URL)   │        │
│  │     │  (Web模式: 代理获取, 不暴露原始Token)     │        │
│  │     ├─ Git Provider Token → StaticSecret(值)    │        │
│  │     │  (本地模式: 直接存储)                     │        │
│  │     └─ API-provided secrets → StaticSecret       │        │
│  │                                                  │        │
│  │ 4b. LLM + MCP 配置                             │        │
│  │     ├─ _configure_llm() → LLM 实例              │        │
│  │     ├─ _add_system_mcp_servers() → 默认MCP     │        │
│  │     │  (含 Tavily 搜索代理)                     │        │
│  │     └─ _merge_custom_mcp_config() → 用户MCP    │        │
│  │                                                  │        │
│  │ 4c. 工具集选择                                  │        │
│  │     ├─ Default Agent → get_default_tools()      │        │
│  │     │  (Terminal/FileEditor/Browser/SubAgents)  │        │
│  │     └─ Planning Agent → get_planning_tools()    │        │
│  │        (PlanFileEditor + 只读工具)              │        │
│  │                                                  │        │
│  │ 4d. AgentSettings.create_agent()                │        │
│  │     └─ _apply_server_agent_overrides()          │        │
│  │        ├─ system_prompt_filename (planning/j2)  │        │
│  │        ├─ LLM tracing metadata (SaaS)           │        │
│  │        └─ Condenser LLM tracing                 │        │
│  └──────────────────────┬──────────────────────────┘        │
│                          │                                  │
│                          ▼                                  │
│  ┌─────────────────────────────────────────────────┐        │
│  │ Step 5: Skills + Hooks 加载                     │        │
│  │ ├─ _load_skills_and_update_agent()              │        │
│  │ │  5种来源: Public/User/Org/Project/Sandbox     │        │
│  │ │  → AgentContext.skills 合并(去重,后覆盖前)    │        │
│  │ └─ _load_hooks_from_workspace()                 │        │
│  │    .openhands/hooks.json → HookConfig           │        │
│  └──────────────────────┬──────────────────────────┘        │
│                          │                                  │
│                          ▼                                  │
│  ┌─────────────────────────────────────────────────┐        │
│  │ Step 6: Plugin 参数注入                         │        │
│  │ ├─ PluginSpec.parameters → 格式化为文本         │        │
│  │ └─ 追加到 initial_message (非系统提示)          │        │
│  └──────────────────────┬──────────────────────────┘        │
│                          │                                  │
│                          ▼                                  │
│  ┌─────────────────────────────────────────────────┐        │
│  │ Step 7: 启动对话                                │        │
│  │ ├─ 路由选择:                                    │        │
│  │ │  OpenHands → POST /api/conversations           │        │
│  │ │  ACP → POST /api/acp/conversations             │        │
│  │ ├─ 保存 AppConversationInfo (SQL)                │        │
│  │ ├─ 注册 EventCallback (SetTitleCallbackProcessor)│        │
│  │ └─ 处理 PendingMessages (排队消息)              │        │
│  └─────────────────────────────────────────────────┘        │
└──────────────────────────────────────────────────────────────┘
```

### 9.6 事件回调与 Webhook 流程

```
┌──────────────────────────────────────────────────────────────┐
│              EventCallback / Webhook 流程                     │
│                                                              │
│  Agent 产生事件 (Event)                                       │
│       │                                                      │
│       ▼                                                      │
│  EventStore 持久化                                            │
│       │                                                      │
│       ▼                                                      │
│  ┌─────────────────────────────────────────────────┐        │
│  │ EventCallbackService 查询匹配的 Callback        │        │
│  │ ├─ 按 conversation_id 过滤                      │        │
│  │ ├─ 按 event type 过滤                           │        │
│  │ └─ 按 status=ACTIVE 过滤                        │        │
│  └──────────────────────┬──────────────────────────┘        │
│                          │                                  │
│                          ▼                                  │
│  ┌─────────────────────────────────────────────────┐        │
│  │ EventCallbackProcessor 执行                      │        │
│  │                                                  │        │
│  │ ├─ SetTitleCallbackProcessor                    │        │
│  │ │  → 轮询 Agent Server 获取标题                 │        │
│  │ │  → 更新 AppConversationInfo.title             │        │
│  │ │                                                │        │
│  │ ├─ LoggingCallbackProcessor                     │        │
│  │ │  → 记录事件日志                               │        │
│  │ │                                                │        │
│  │ └─ Enterprise 扩展:                              │        │
│  │    ├─ GitHubV1CallbackProcessor                  │        │
│  │    │  → PR 评论/状态更新                         │        │
│  │    ├─ SlackV1CallbackProcessor                   │        │
│  │    │  → Slack 消息通知                           │        │
│  │    ├─ JiraV1CallbackProcessor                    │        │
│  │    │  → Jira Issue 状态同步                      │        │
│  │    ├─ GitLabV1CallbackProcessor                  │        │
│  │    │  → MR 评论/状态更新                         │        │
│  │    └─ BitbucketV1CallbackProcessor               │        │
│  │       → PR 评论/状态更新                         │        │
│  └──────────────────────┬──────────────────────────┘        │
│                          │                                  │
│                          ▼                                  │
│  ┌─────────────────────────────────────────────────┐        │
│  │ EventCallbackResult 状态跟踪                     │        │
│  │ ├─ SUCCESS → 记录成功                            │        │
│  │ ├─ FAILED → 记录失败 + 错误分类                 │        │
│  │ │  (budget_exceeded/model_error/runtime_error/  │        │
│  │ │   timeout/user_cancelled/unknown)             │        │
│  │ └─ RETRY → 重试机制                              │        │
│  └─────────────────────────────────────────────────┘        │
└──────────────────────────────────────────────────────────────┘
```

### 9.7 前端 V1 事件流驱动架构

```
┌──────────────────────────────────────────────────────────────┐
│              前端 V1 事件流驱动架构                            │
│                                                              │
│  ┌─────────────┐                                             │
│  │ Agent Server │                                             │
│  │  WebSocket   │                                             │
│  └──────┬──────┘                                             │
│         │ JSON events                                        │
│         ▼                                                    │
│  ┌─────────────────────────────────────────────────┐        │
│  │ ConversationWebSocketProvider                    │        │
│  │ ├─ useWebSocket() 管理 WebSocket 连接           │        │
│  │ │  ├─ 自动重连 (maxAttempts)                    │        │
│  │ │  └─ 连接状态: CONNECTING/OPEN/CLOSED/CLOSING  │        │
│  │ ├─ 消息解析: JSON → OpenHandsEvent              │        │
│  │ └─ sendMessage(): 发送用户消息                  │        │
│  └──────────────────────┬──────────────────────────┘        │
│                          │                                  │
│                          ▼                                  │
│  ┌─────────────────────────────────────────────────┐        │
│  │ useEventStore (Zustand)                          │        │
│  │ ├─ events: OHEvent[] (V0+V1混合)                │        │
│  │ ├─ eventIds: Set (O(1)去重)                     │        │
│  │ ├─ uiEvents: OHEvent[] (UI相关事件)             │        │
│  │ ├─ addEvent(): 去重 + 时间排序                  │        │
│  │ └─ clearEvents()                                │        │
│  └──────────────────────┬──────────────────────────┘        │
│                          │                                  │
│          ┌───────────────┼───────────────┐                  │
│          │               │               │                  │
│          ▼               ▼               ▼                  │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐       │
│  │ Zustand      │ │ Zustand      │ │ Zustand      │       │
│  │ Stores       │ │ Stores       │ │ Stores       │       │
│  │              │ │              │ │              │       │
│  │ browserStore │ │ v1ConvState  │ │ metricsStore │       │
│  │ commandStore │ │ errorMessage │ │ agentStore   │       │
│  │ optimisticMsg│ │ convStore    │ │ modelStore   │       │
│  └──────┬───────┘ └──────┬───────┘ └──────┬───────┘       │
│         │                │                │                 │
│         ▼                ▼                ▼                 │
│  ┌─────────────────────────────────────────────────┐        │
│  │ React Components (事件驱动渲染)                  │        │
│  │ ├─ ChatInterface: 消息列表 + 输入框             │        │
│  │ ├─ EventMessage: 单条事件渲染                   │        │
│  │ │  ├─ ActionEvent → 工具调用展示                │        │
│  │ │  ├─ ObservationEvent → 工具结果展示           │        │
│  │ │  ├─ MessageEvent → 用户/AI消息                │        │
│  │ │  └─ CondensationEvent → 压缩摘要              │        │
│  │ ├─ AgentStatus: 运行状态展示                    │        │
│  │ ├─ Browser: 浏览器操作展示                      │        │
│  │ └─ TaskTracking: 任务进度追踪                   │        │
│  └─────────────────────────────────────────────────┘        │
└──────────────────────────────────────────────────────────────┘
```

---

## 10. 验证说明

本报告所有核心描述均经过源码逐行验证：

| 验证项 | 验证方法 | 结果 |
|--------|----------|------|
| Namespace Package | 读取 openhands/__init__.py，确认 pkgutil.extend_path | 已确认 |
| Agent 继承结构 | 读取 agent.py 类定义 | CriticMixin + ResponseDispatchMixin + AgentBase |
| Agent.step() 流程 | 逐行阅读 step() 方法（475-603行） | 含 pending_actions/hook/condensation/异常处理 |
| Conversation 状态机 | 逐行阅读 LocalConversation.run()（745-888行） | 8种状态，Hook可拒绝FINISHED |
| LLM 双模式 | 逐行阅读 completion()和responses() | Completion API + Responses API |
| App Server DI | 逐行阅读 AppServerConfig + config_from_env | 17个Injector，环境变量自动选择 |
| Enterprise 扩展 | 逐行阅读 get_impl/import_from + ServerConfig | importlib动态导入+字符串类引用 |
| 源码行数 | find + wc -l 重新统计 | 与报告中数据一致 |
| Hook 系统 | 逐行阅读 hook_loader.py + live_status 中的 _load_hooks | Agent Server /api/hooks 端点加载 |
| Skill 多源加载 | 逐行阅读 skill_loader.py + load_and_merge_all_skills | 5种来源，agent-server /api/skills 统一 |
| EventCallback | 逐行阅读 event_callback_models + webhook_router | DiscriminatedUnionMixin + 6种Processor |
| Secret 管理 | 逐行阅读 _setup_secrets_for_git_providers | LookupSecret(Web) + StaticSecret(Local) |
| ACP Agent | 逐行阅读 _build_acp_start_conversation_request + settings_models | 双模式路由 acp/conversations |
| Planning Agent | 逐行阅读 _apply_server_agent_overrides + get_planning_tools | 独立工具集 + PLAN.md |
| Suggested Task | 逐行阅读 service_types + _apply_suggested_task | 5种任务类型 + Jinja2模板 |
| Sandbox Grouping | 逐行阅读 settings_models + _get_sandbox_grouping_strategy | 5种策略 |
| Analytics | 逐行阅读 analytics_service.py | PostHog + 同意门控 + OSS/SaaS双模式 |
| 前端 V1 事件流 | 逐行阅读 use-event-store + conversation-websocket-context | Zustand + WebSocket + 事件去重排序 |
| 对话启动流程 | 逐行阅读 _start_app_conversation (300-460行) | 10+步骤完整组装链 |
