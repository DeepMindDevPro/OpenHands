# OpenHands 项目系统性学习指南

> 基于对项目全部源码的深度阅读，涵盖整体架构设计、设计亮点、设计缺陷，以及系统性学习问题。

---

## 一、整体架构设计

### 1.1 系统拓扑

OpenHands 采用**多层分离架构**，核心由以下四大子系统组成：

```
┌─────────────────────────────────────────────────────────┐
│                    用户层 (User Layer)                    │
│  Web UI (React/SPA)  │  CLI  │  SDK (Python)            │
└──────────┬────────────┴───────┴──────────────────────────┘
           │  HTTP/SSE
┌──────────▼───────────────────────────────────────────────┐
│              App Server (FastAPI)                         │
│  ┌────────────┬──────────────┬──────────────┬──────────┐ │
│  │ 会话管理   │ 设置/配置    │ Git 集成     │ MCP 代理 │ │
│  │ Conversation│ Settings    │ Integrations │ MCP      │ │
│  └─────┬──────┴──────┬───────┴──────────────┴─────┬────┘ │
│        │             │                            │      │
│  ┌─────▼──────┐ ┌────▼─────────┐          ┌──────▼────┐ │
│  │ 事件系统   │ │ 依赖注入     │          │ 安全/JWT  │ │
│  │ Event      │ │ Injector     │          │ Security  │ │
│  └────────────┘ └──────────────┘          └───────────┘ │
└──────────┬───────────────────────────────────────────────┘
           │  HTTP (Agent Server API)
┌──────────▼───────────────────────────────────────────────┐
│              Agent Server (独立进程/容器)                  │
│  ┌──────────────┬──────────────┬───────────────────────┐ │
│  │ Agent 执行   │ 工具调用     │ 技能/Hook 加载        │ │
│  │ CodeActAgent │ Tools        │ Skills/Hooks          │ │
│  └──────────────┴──────────────┴───────────────────────┘ │
└──────────┬───────────────────────────────────────────────┘
           │  Docker API / Process
┌──────────▼───────────────────────────────────────────────┐
│              Sandbox (沙箱运行时)                          │
│  ┌──────────┬──────────┬──────────┬───────────────────┐ │
│  │ 终端     │ 文件编辑 │ 浏览器   │ VSCode (可选)     │ │
│  │ Bash     │ Editor   │ Browser  │ VSCode Server     │ │
│  └──────────┴──────────┴──────────┴───────────────────┘ │
└──────────────────────────────────────────────────────────┘
```

### 1.2 核心模块职责

| 模块 | 路径 | 职责 |
|------|------|------|
| App Server | `openhands/app_server/` | Web 应用主服务，管理会话、设置、集成、MCP 代理 |
| Agent Server | `openhands-agent-server` (pip包) | Agent 执行引擎，运行在沙箱内部 |
| SDK | `openhands-sdk` (pip包) | 核心 Agent/LLM/工具抽象，跨进程共享 |
| Sandbox | `app_server/sandbox/` | 沙箱生命周期管理（Docker/Process/Remote） |
| Frontend | `frontend/` | React SPA，TanStack Query + Zustand 状态管理 |
| Enterprise | `enterprise/` | SaaS 扩展：认证、计费、多租户、分析 |
| Tools | `openhands-tools` (pip包) | 预置工具集（Bash、Editor、Browser 等） |

### 1.3 关键数据流

**会话启动流程：**
```
用户请求 → AppConversationRouter
  → LiveStatusAppConversationService.start_app_conversation()
    → _find_running_sandbox_for_user() (沙箱复用策略)
    → SandboxService.start_sandbox() / resume_sandbox()
    → _wait_for_sandbox_start() (轮询等待)
    → _configure_llm_and_mcp() (配置 LLM + MCP)
    → _setup_secrets_for_git_providers() (注入 Git 凭据)
    → load_and_merge_all_skills() (加载技能)
    → Agent Server /api/conversations (创建会话)
    → 发送初始消息
```

**消息发送流程：**
```
用户消息 → AppConversationRouter.send_message()
  → 转发到 Agent Server /api/conversations/{id}/messages
    → Agent 执行循环 (LLM 推理 → 工具调用 → 观察结果)
    → 事件通过 WebSocket/SSE 推送回前端
```

---

## 二、设计亮点

### 2.1 依赖注入体系（Injector Pattern）

**位置：** `openhands/app_server/services/injector.py`

OpenHands 设计了一套基于泛型的依赖注入框架：

```python
class Injector(Generic[T], ABC):
    async def inject(self, state: InjectorState, request: Request | None = None) -> AsyncGenerator[T, None]
    async def depends(self, request: Request) -> AsyncGenerator[T, None]  # FastAPI Depends 兼容
```

**亮点：**
- 每个服务（Sandbox、Event、UserContext、JWT 等）都有对应的 Injector，支持运行时切换实现
- `DiscriminatedUnionMixin` 支持基于配置的判别联合类型，实现 OSS/SaaS 模式切换
- 与 FastAPI 的 `Depends` 无缝集成，无需额外框架
- 支持嵌套注入：一个 Injector 的 `inject()` 内可调用另一个 Injector

**学习问题：**
1. Injector 如何实现与 FastAPI `Depends` 的兼容？`depends()` 方法的 `request.state` 如何传递注入状态？
2. `DiscriminatedUnionMixin` 如何实现 OSS/SaaS 模式的运行时切换？配置从哪里读取？
3. 如果要新增一个服务（如 RateLimitService），需要创建哪些类？请描述完整的注入链路。

### 2.2 多沙箱策略（Sandbox Grouping Strategy）

**位置：** `openhands/app_server/app_conversation/app_conversation_models.py` + `live_status_app_conversation_service.py`

支持 5 种沙箱分组策略：

| 策略 | 行为 |
|------|------|
| `NO_GROUPING` | 每个会话独立沙箱 |
| `GROUP_BY_NEWEST` | 复用最新创建的沙箱 |
| `LEAST_RECENTLY_USED` | 复用最久未使用的沙箱 |
| `FEWEST_CONVERSATIONS` | 复用会话数最少的沙箱 |
| `ADD_TO_ANY` | 复用任何可用沙箱 |

**亮点：**
- 策略可在用户设置中动态配置，无需重启
- 每个沙箱有最大会话数限制（`max_num_conversations_per_sandbox`），超出后自动创建新沙箱
- 沙箱暂停后支持 resume，避免冷启动开销

**学习问题：**
4. `_select_sandbox_by_strategy()` 方法中的会话计数是如何实现的？为什么采用逐个查询而非批量查询？
5. 沙箱暂停（PAUSED）和恢复（resume）的生命周期如何管理？Docker 沙箱和 Process 沙箱的恢复机制有何不同？
6. 如果所有沙箱都达到最大会话数限制，系统如何处理？有无排队机制？

### 2.3 三种沙箱后端（Docker / Process / Remote）

**位置：** `openhands/app_server/sandbox/`

| 后端 | 适用场景 | 隔离级别 |
|------|----------|----------|
| `DockerSandboxService` | 生产/开发 | 容器级隔离 |
| `ProcessSandboxService` | 无 Docker 环境 | 进程级隔离 |
| `RemoteSandboxService` | Kubernetes/云部署 | 远程运行时 |

**亮点：**
- 统一的 `SandboxService` 抽象接口，上层代码无需关心后端实现
- Docker 沙箱支持 Host Network 和 Bridge Network 两种网络模式
- Remote 沙箱维护本地 `StoredRemoteSandbox` 数据库，弥补远程 API 的信息缺失
- Process 沙箱的全局 `_processes` 字典实现轻量级进程管理

**学习问题：**
7. 三种沙箱后端的 `start_sandbox()` 实现差异是什么？各自如何生成 session_api_key？
8. Docker 沙箱的端口映射逻辑（`_container_to_sandbox_info()`）如何处理 Host Network 和 Bridge Network 两种模式？
9. Remote 沙箱为什么需要 `StoredRemoteSandbox` 本地存储？远程 API 有哪些信息缺失？

### 2.4 事件回调解耦（Event Callback System）

**位置：** `openhands/app_server/event_callback/`

事件系统采用"存储-回调"分离架构：

- **EventService**：负责事件的持久化存储（文件系统/S3/GCS）
- **EventCallbackService**：负责事件触发后的回调处理（如自动设置标题）
- **SetTitleCallbackProcessor**：监听事件，自动从对话内容提取标题

**亮点：**
- 事件存储和回调处理完全解耦，可独立扩展
- 支持多种存储后端：本地文件系统、AWS S3、Google Cloud Storage
- 回调处理器可插拔，通过 `EventCallback` 模型持久化配置

**学习问题：**
10. EventServiceBase 如何实现用户级隔离？`get_conversation_path()` 方法中的 `user_id` 前缀如何保证安全性？
11. 新增一个 EventCallbackProcessor（如自动总结处理器）需要实现哪些接口？如何注册到系统中？
12. 事件存储的 `_load_event()` 和 `_store_event()` 为什么设计为同步方法？异步调用时如何避免阻塞事件循环？

### 2.5 LLM 配置的多层解析（LLM Resolution Chain）

**位置：** `openhands/app_server/utils/llm.py` + `config.py`

LLM 配置经过多层解析：

```
用户设置的 model → openhands/ 前缀检测 → litellm_proxy/ 转换
  → base_url 解析（用户显式 > Provider URL > SDK 默认）
  → resolve_provider_llm_base_url() 统一处理
```

**亮点：**
- `resolve_llm_base_url()` 是 base_url 解析的单一真相源，个人设置和企业组织设置两条路径共用
- 支持 OpenHands 托管模型（`openhands/` 前缀）和自带 API Key（BYOR）两种模式
- `StrictLLM` 子类禁止未知字段，防止前端传错参数时静默忽略

**学习问题：**
13. `resolve_provider_llm_base_url()` 中，为什么 `openhands/` 前缀的模型在 SDK 默认 proxy URL 时需要替换为部署 Provider URL？
14. LLM Profiles 系统（`LLMProfiles`）如何管理多个 LLM 配置？`active` 字段如何控制当前生效的配置？
15. 京东云 Qwen 35B 模型（OpenAI 兼容 API）应如何配置？model、base_url、api_key 各应设置什么值？

### 2.6 Secret 安全体系（LookupSecret / StaticSecret）

**位置：** `openhands/sdk/secret.py` + `live_status_app_conversation_service.py`

两种 Secret 类型：
- **StaticSecret**：直接存储 Secret 值（用于本地/无 Web URL 环境）
- **LookupSecret**：存储 URL + Headers，运行时动态获取（用于 SaaS 环境，Secret 值不离开服务端）

**亮点：**
- SaaS 模式下，Git Provider Token 通过 JWT 签名的 Access Token + Lookup URL 动态获取
- Secret 值只在 `SaaS → Sandbox` 方向流动，永不经过 SDK 客户端
- 日志中的 Secret 自动脱敏（`redact_text_secrets`、`redact_api_key_literals`）

**学习问题：**
16. `_setup_secrets_for_git_providers()` 方法中，有 `web_url` 和无 `web_url` 时的 Secret 类型有何不同？为什么？
17. LookupSecret 的动态获取流程是什么？JWT Access Token 的有效期如何控制？
18. Secret 脱敏机制如何工作？`sanitize_config()` 函数处理了哪些类型的敏感信息？

### 2.7 MCP 代理架构（MCP Proxy Pattern）

**位置：** `openhands/app_server/mcp/mcp_router.py`

使用 FastMCP 构建服务端 MCP 代理：

- **Tavily 代理**：将 Tavily API Key 隐藏在服务端，沙箱通过 MCP 协议调用搜索功能
- **Git 集成工具**：通过 MCP 暴露 Git 操作（创建 PR、添加评论等），沙箱无需直接访问 Git API
- **命名空间挂载**：`mcp_server.mount(namespace='tavily', server=proxy_server)` 实现工具命名空间隔离

**亮点：**
- API Key 不暴露给沙箱，安全性大幅提升
- 统一的 MCP 协议接口，沙箱无需了解底层 API 细节
- 支持用户自定义 MCP 服务器配置（`_merge_custom_mcp_config()`）

**学习问题：**
19. `init_tavily_proxy()` 为什么在 App 创建之前调用？如果 Tavily API Key 未配置，系统如何降级？
20. MCP 工具调用的认证流程是什么？`X-Session-API-Key` 和 `X-OpenHands-ServerConversation-ID` 各起什么作用？
21. 如何添加一个新的 MCP 代理（如 Jira 集成）？需要修改哪些文件？

### 2.8 技能加载的多源合并（Multi-Source Skill Loading）

**位置：** `openhands/app_server/app_conversation/skill_loader.py` + `app_conversation_service_base.py`

技能来源按优先级合并：
1. **公共技能**（OpenHands/skills GitHub 仓库）
2. **用户技能**（`~/.openhands/skills/`）
3. **组织技能**（`{org}/.openhands` 仓库）
4. **项目技能**（`.agents/skills/`、`.openhands/microagents/`）
5. **沙箱技能**（通过暴露的 URL 提供）

**亮点：**
- App Server 作为薄代理，将技能加载委托给 Agent Server 的 `/api/skills` 端点
- 技能合并采用"后覆盖前"策略，项目级技能可覆盖公共技能
- `_merge_skills()` 方法按名称去重，确保同一技能只保留最高优先级版本

**学习问题：**
22. `build_org_config()` 和 `build_sandbox_config()` 各传递什么信息给 Agent Server？为什么认证信息只在 org_config 中？
23. Microagent 的 trigger 机制如何工作？关键词触发和任务触发的区别是什么？
24. 技能加载失败时（如 Agent Server 不可用），系统如何降级？对用户有什么影响？

### 2.9 前端数据访问层架构（API → Hooks → Components）

**位置：** `frontend/src/api/` + `frontend/src/hooks/`

严格的三层架构：
```
UI Components → TanStack Query Hooks → Data Access Layer (api/) → Backend API
```

- **Query Hooks**（`hooks/query/`）：数据读取，自动缓存和去重
- **Mutation Hooks**（`hooks/mutation/`）：数据写入，自动失效缓存

两种设置保存模式：
- **Pattern 1（即时保存）**：API Keys、Secrets、MCP Servers — 每次操作立即保存
- **Pattern 2（表单保存）**：应用设置、LLM 配置 — 聚合后手动保存

**亮点：**
- TanStack Query 提供缓存、去重、自动刷新，避免冗余请求
- 两种保存模式针对不同场景优化 UX
- API 服务层强制类型安全，TypeScript 类型与后端 Pydantic 模型对应

**学习问题：**
25. 为什么 API 层不允许在 UI 组件中直接调用？TanStack Query 的缓存策略如何影响数据一致性？
26. Pattern 1 和 Pattern 2 的 `isDirty` 状态管理有何不同？各适用于什么场景？
27. 前端的 WebSocket 连接如何与 TanStack Query 缓存协同工作？实时事件如何触发缓存失效？

### 2.10 Condenser 上下文压缩系统

**位置：** `config.template.toml` [condenser] + `openhands/sdk/`

6 种上下文压缩策略：

| 类型 | 机制 | 适用场景 |
|------|------|----------|
| `noop` | 不压缩 | 短对话 |
| `observation_masking` | 遮蔽旧观察 | 长对话、隐私敏感 |
| `recent` | 只保留最近 N 个事件 | 上下文窗口极小 |
| `llm` | LLM 摘要压缩 | 通用场景 |
| `amortized` | 渐进遗忘 | 超长对话 |
| `llm_attention` | LLM 注意力评分 | 精确上下文选择 |

**亮点：**
- 可按 Agent 独立配置 Condenser
- LLM Condenser 支持独立的 LLM 配置（`llm_config = "condenser"`），可使用更便宜的模型
- 上下文压缩与 Agent 解耦，无需修改 Agent 代码即可切换策略

**学习问题：**
28. Amortized Condenser 的"渐进遗忘"算法如何决定哪些事件需要遗忘？`keep_first` 参数保护了什么？
29. LLM Attention Condenser 的注意力评分机制是什么？与 LLM Summarizing Condenser 的核心区别？
30. Condenser 的 `max_size` 参数触发压缩的时机是什么？压缩是同步还是异步的？

### 2.11 会话启动的异步任务编排（Start Task Generator）

**位置：** `live_status_app_conversation_service.py` `_start_app_conversation()` + `AppConversationStartTask`

会话启动是一个多阶段异步过程，通过 `AsyncGenerator` 编排：

```
WORKING → WAITING_FOR_SANDBOX → PREPARING_REPOSITORY →
RUNNING_SETUP_SCRIPT → SETTING_UP_GIT_HOOKS →
SETTING_UP_SKILLS → STARTING_CONVERSATION → READY/ERROR
```

每个阶段通过 `yield task` 将状态变更推送给调用者，实现实时进度反馈。

**亮点：**
- Generator 模式天然适合多阶段异步编排，调用者可实时获取进度
- `AppConversationStartTask` 的每个状态字段（`sandbox_id`、`agent_server_url`、`app_conversation_id`）在不同阶段逐步填充
- 前端通过 SSE 流式消费这些状态更新，实现启动进度条

**学习问题：**
65. `_start_app_conversation()` 为什么选择 `AsyncGenerator` 而非 `async Task` + 回调？如果中间阶段失败（如 setup_script 超时），Generator 如何清理已分配的资源？
66. `AppConversationStartTaskStatus` 的 8 个状态中，哪些是阻塞的（等待外部服务），哪些是瞬时的？前端如何根据这些状态渲染进度？
67. `PendingMessageService` 的 `_process_pending_messages()` 如何处理用户在沙箱启动期间发送的消息？消息的 `update_conversation_id()` 为什么需要将临时 task-id 映射到真实 conversation-id？

### 2.12 ACP Agent 双轨执行架构

**位置：** `live_status_app_conversation_service.py` `_build_acp_start_conversation_request()`

系统同时支持两种 Agent 类型：
- **OpenHands Agent**（`CodeActAgent`）：通过 LLM API 直接调用，Agent Server 管理执行循环
- **ACP Agent**（`ACPAgent`）：启动子进程（如 Claude Code、Codex CLI），通过 ACP 协议通信

**亮点：**
- ACP Agent 将凭据通过环境变量注入子进程，而非 LLM API Key 方式
- `_acp_provider_env()` 自动根据 `acp_server` 类型（claude-code/codex/gemini-cli）映射 API Key 到正确的环境变量
- ACP Agent 的 secrets 通过 `AgentContext.secrets` 以 `<CUSTOM_SECRETS>` 块注入提示词，兼顾 SDK 兼容性（`_sdk_supports_acp_secrets` 特性检测）

**学习问题：**
68. ACP Agent 和 OpenHands Agent 的 `StartConversationRequest` 有什么结构差异？为什么 ACP 不需要 `LLM` 对象？
69. `_acp_provider_env()` 中的 `_SERVER_KEY_MAP` 硬编码了三种 ACP 服务器。如何扩展支持新的 ACP 服务器？`api_key_env_var` 字段如何消除硬编码？
70. `_sdk_supports_acp_secrets` 的特性检测（检查 `json_schema_extra.get('acp_compatible')`）为什么比版本号检测更可靠？这种模式有什么潜在问题？

### 2.13 Sandbox Spec 环境变量自动转发

**位置：** `sandbox_spec_service.py` `get_agent_server_env()`

App Server 自动将特定前缀的环境变量转发给 Agent Server 容器：

```python
AUTO_FORWARD_PREFIXES = ('LLM_', 'LMNR_')
```

- `LLM_*`：LLM 配置（超时、重试等）
- `LMNR_*`：Laminar 监控/分析配置
- `OH_AGENT_SERVER_ENV`：JSON 格式的显式覆盖（优先级最高）

**亮点：**
- 避免在两容器架构中重复配置 LLM 参数
- 显式 JSON 覆盖优先级高于自动转发，支持精确控制
- 前缀匹配而非白名单，新增配置项无需修改代码

**学习问题：**
71. `AUTO_FORWARD_PREFIXES` 为什么只包含 `LLM_` 和 `LMNR_`？如果添加新的监控工具（如 OpenTelemetry），应如何扩展？
72. `OH_AGENT_SERVER_ENV` JSON 覆盖的优先级高于自动转发。如果用户同时设置了 `LLM_TIMEOUT` 环境变量和 `OH_AGENT_SERVER_ENV` 中的 `LLM_TIMEOUT`，哪个生效？

### 2.14 Plugin 系统与动态技能注入

**位置：** `app_conversation_models.py` `PluginSpec` + `live_status_app_conversation_service.py` `_construct_initial_message_with_plugin_params()`

Plugin 系统允许在会话启动时注入远程技能和配置：

- `PluginSpec` 继承 SDK 的 `PluginSource`，增加了 `parameters` 字段
- Plugin 参数被格式化后追加到初始消息中，让 Agent 了解配置上下文
- SDK Plugin 通过 `StartConversationRequest.plugins` 传递，由 Agent Server 加载

**亮点：**
- Plugin 参数与消息内容融合，Agent 无需额外理解 Plugin 协议
- 单 Plugin 和多 Plugin 的格式化逻辑不同（多 Plugin 按名称分组）
- Plugin 加载失败不阻塞会话启动

**学习问题：**
73. Plugin 参数追加到初始消息的 `TextContent` 末尾，如果消息内容是图片或其他非文本类型，如何处理？
74. Plugin 的 `source` 字段支持哪些格式（GitHub 仓库、本地路径、URL）？Agent Server 如何解析和加载这些源？

### 2.15 WebSocket 重连与双连接架构

**位置：** `frontend/src/hooks/use-websocket.ts` + `conversation-websocket-context.tsx`

前端 WebSocket 连接采用双连接架构：
- **主连接**：连接 App Server，接收会话列表状态更新
- **会话连接**：直接连接 Agent Server 沙箱，接收事件流

**亮点：**
- `useWebSocket` Hook 支持自动重连（3 秒间隔，可配置最大次数）
- `WeakSet` 跟踪允许重连的 WebSocket 实例，防止已断开的旧实例触发重连
- `extractBaseHost()` 智能处理 localhost 与外部访问的 URL 转换
- `extractPathPrefix()` 支持代理部署的路径前缀提取

**学习问题：**
75. 为什么需要双 WebSocket 连接？主连接和会话连接分别负责什么类型的事件？如果一个连接断开，另一个如何感知？
76. `useWebSocket` 的 `WeakSet` 重连控制机制如何避免"幽灵重连"（旧 WebSocket 实例触发的不必要重连）？
77. `extractBaseHost()` 中，当浏览器从外部访问 localhost 沙箱时，如何替换 hostname？这在 NAT/代理环境中是否可靠？

### 2.16 子会话与父子关系（Parent-Child Conversations）

**位置：** `app_conversation_models.py` `parent_conversation_id` + `live_status_app_conversation_service.py` `_inherit_configuration_from_parent()`

会话支持父子关系：
- 子会话自动继承父会话的 `sandbox_id`、`selected_repository`、`selected_branch`、`git_provider`、`llm_model`
- 用于 Resolver 场景：主会话处理 Issue/PR，子会话执行具体任务

**亮点：**
- 继承逻辑只在字段为空时生效，显式指定优先于继承
- 同一沙箱内的子会话共享工作空间，避免重复克隆仓库
- `sub_conversation_ids` 列表支持反向查找

**学习问题：**
78. 子会话继承 `sandbox_id` 意味着与父会话共享沙箱。这如何影响资源隔离？子会话能否独立销毁？
79. `_inherit_configuration_from_parent()` 只在请求字段为空时继承。如果用户想覆盖父会话的 LLM 模型，如何实现？

### 2.17 Git Setup 自动化（pre-commit hooks + setup.sh）

**位置：** `app_conversation_service_base.py` `run_setup_scripts()`

沙箱启动时自动执行：
1. `.openhands/setup.sh`：安装项目依赖
2. `.openhands/pre-commit.sh`：安装 Git pre-commit hooks
3. 克隆仓库（如果选择了 repository）

**亮点：**
- Setup 脚本让项目环境一键就绪，开发者无需手动配置
- Pre-commit hooks 确保 Agent 的代码修改符合项目规范
- 执行失败不阻塞会话启动（降级为警告）

**学习问题：**
80. `run_setup_scripts()` 的执行失败降级策略是什么？如果 setup.sh 安装了部分依赖后失败，沙箱处于什么状态？

---

## 三、设计缺陷

### 3.1 巨型服务类（God Object）

**位置：** `live_status_app_conversation_service.py`（84.6KB，约 1200+ 行）

`LiveStatusAppConversationService` 承担了过多职责：
- 会话 CRUD
- 沙箱生命周期管理
- LLM/MCP 配置
- Secret 注入
- 技能加载
- 子会话继承
- Agent 类型覆盖

**问题：**
- 单个类 84KB，修改任何功能都需要理解整个类
- 测试困难：mock 依赖多达 15+ 个
- 违反单一职责原则

**学习问题：**
31. 如果要将 `LiveStatusAppConversationService` 拆分为更小的服务，你会如何划分？请给出具体的类名和职责。
32. 该类中哪些方法适合提取为独立的策略类（如 LLM 配置策略、Secret 注入策略）？

### 3.2 全局状态管理

**位置：** `process_sandbox_service.py` 中的 `_processes: dict[str, ProcessInfo] = {}`

Process 沙箱使用模块级全局字典存储进程信息：

**问题：**
- 多进程/多线程环境下不安全
- 进程重启后状态丢失
- 无法跨实例共享（不支持水平扩展）

**学习问题：**
33. 如何将 `_processes` 字典替换为持久化存储？需要考虑哪些一致性保证？
34. Remote 沙箱的 `StoredRemoteSandbox` 数据库方案是否可以应用到 Process 沙箱？

### 3.3 路由文件过大

**位置：** `app_conversation_router.py`（50.2KB）

单个路由文件包含了所有会话相关的端点，包括：
- 会话 CRUD
- 消息发送
- 沙箱管理
- 事件流
- Git 操作

**问题：**
- 50KB 的路由文件难以维护
- 代码审查困难
- 合并冲突频繁

**学习问题：**
35. 如何按功能域拆分 `app_conversation_router.py`？拆分后如何保持 API 路径不变？

### 3.4 同步阻塞调用

**位置：** `docker_sandbox_service.py` 中的 Docker API 调用

Docker Python SDK 是同步库，在异步事件循环中直接调用会阻塞：

```python
# Docker API 是同步的，会阻塞事件循环
containers = self.docker_client.containers.list()
```

**问题：**
- 阻塞异步事件循环，影响并发性能
- 在高负载下可能导致请求超时

**学习问题：**
36. 为什么 `DockerSandboxService` 的文档注释说"probably acceptable"？在什么场景下不可接受？
37. 如何使用 `run_in_executor()` 或独立线程池来包装同步 Docker API 调用？

### 3.5 硬编码的模型列表同步问题

**位置：** `AGENTS.md` 第 394-443 行描述的模型配置流程

添加新 LLM 模型需要修改 5+ 个文件：
1. `frontend/src/utils/verified-models.ts`
2. `openhands/cli/utils.py`
3. `openhands/utils/llm.py`（注意：文件路径已过时）
4. `openhands/llm/llm.py`（注意：文件路径已过时）
5. SDK 的 `verified_models.py`

**问题：**
- 多处手动同步，容易遗漏
- AGENTS.md 中的文件路径与实际代码结构不一致
- 模型验证数组分散在前端、后端、SDK 三个代码库

**学习问题：**
38. 如何设计一个统一的模型注册表（Model Registry），使得添加新模型只需修改一处？
39. SDK 的 `VERIFIED_MODELS` 与 litellm 的模型目录是什么关系？为什么需要额外维护？

### 3.6 CORS 安全隐患

**位置：** `middleware.py` `LocalhostCORSMiddleware`

```python
# Allow any origin when no specific origins are configured (development mode)
if hostname in ['localhost', '127.0.0.1']:
    return True
# 无配置时允许所有来源
logging.warning(...)
return True
```

**问题：**
- 无 CORS 配置时默认允许所有来源，生产环境风险高
- localhost 白名单无法关闭，可能被恶意网页利用
- 仅通过 warning 日志提醒，容易忽视

**学习问题：**
40. 在生产环境中，如果忘记设置 `OH_PERMITTED_CORS_ORIGINS`，会有什么安全后果？
41. 如何改进 CORS 配置，使其在无显式配置时默认拒绝而非默认允许？

### 3.7 事件存储的文件系统依赖

**位置：** `event/filesystem_event_service.py`

事件默认存储在本地文件系统：

**问题：**
- 不支持多实例部署（文件系统不共享）
- 无索引，查询效率低
- 大量事件时文件系统性能下降
- 与数据库存储的事件回调不匹配

**学习问题：**
42. 为什么系统同时使用文件系统存储事件和数据库存储事件回调？这种混合存储有哪些一致性问题？
43. 如果要将事件存储迁移到数据库，需要考虑哪些性能和迁移问题？

### 3.8 错误处理不一致

**位置：** 多处

错误处理策略不统一：
- 有些地方用 `SandboxError` 自定义异常
- 有些地方用 `HTTPException`
- 有些地方静默捕获并返回空列表
- 有些地方 `logger.exception()` 后继续执行

**问题：**
- 调试困难：静默吞没错误掩盖了真实问题
- 错误恢复路径不可预测
- 前端无法区分"无数据"和"出错"

**学习问题：**
44. 项目中存在哪些不同的错误处理模式？如何统一为一致的错误处理策略？
45. `load_and_merge_all_skills()` 返回空列表而非抛出异常，这种降级策略在什么情况下会掩盖严重问题？

### 3.9 配置分散

**位置：** 多处

配置来源分散在：
- 环境变量（`OH_` 前缀）
- `config.toml` 文件
- 数据库（用户设置、组织设置）
- SDK 默认值
- 硬编码常量

**问题：**
- 配置优先级不透明
- 同一配置在不同位置有不同名称（如 `LLM_BASE_URL` vs `OPENHANDS_PROVIDER_BASE_URL`）
- 向后兼容的遗留变量增加维护负担

**学习问题：**
46. `config_from_env()` 中的 `from_env(AppServerConfig, 'OH')` 如何处理配置优先级？环境变量如何映射到 Pydantic 模型字段？
47. 遗留环境变量（如 `FILE_STORE_PATH`、`LLM_BASE_URL`）的迁移策略是什么？如何安全地废弃旧变量？

### 3.10 前端状态管理分裂

**位置：** `frontend/src/`

前端同时使用：
- Zustand（全局状态）
- TanStack Query（服务端状态缓存）
- React Router 状态（路由状态）
- Local Storage（持久化设置）

**问题：**
- 状态来源不统一，容易出现不一致
- 服务端状态与本地状态的同步边界模糊
- 不同状态管理方式的调试工具不同

**学习问题：**
48. Zustand 和 TanStack Query 在前端各负责什么类型的状态？边界在哪里？
49. 如果服务端状态和本地状态出现冲突（如并发修改），系统如何解决？

### 3.11 沙箱销毁无优雅关闭

**位置：** `docker_sandbox_service.py` `delete_sandbox()`

```python
if container.status in ['running', 'paused']:
    container.stop(timeout=10)
container.remove()
```

**问题：**
- `stop(timeout=10)` 硬编码超时，Agent 正在执行的长时间任务可能被强制中断
- 无通知机制告知 Agent Server 即将关闭
- 容器内未保存的工作可能丢失
- 关联的 `openhands-workspace-{sandbox_id}` Volume 删除逻辑是 best-effort，失败静默忽略

**学习问题：**
81. 如何实现优雅的沙箱关闭？需要向 Agent Server 发送什么信号？Agent 正在执行 LLM 推理时如何处理？
82. Volume 删除失败（如 Volume 被其他容器引用）的后果是什么？是否会泄漏存储资源？

### 3.12 会话启动无超时上限

**位置：** `live_status_app_conversation_service.py` `_start_app_conversation()`

会话启动的 `_wait_for_sandbox_start()` 使用 `sandbox_startup_timeout`，但整体 `_start_app_conversation()` 没有总超时：

**问题：**
- 如果 setup.sh 执行时间无限长，会话启动可能永远不返回
- 前端 SSE 连接可能因代理超时断开
- 无重试机制：如果某个阶段失败（如 Agent Server 返回 500），用户必须重新发起

**学习问题：**
83. 如何为整个会话启动流程设置总超时？各阶段的超时如何分配？
84. 如果 Agent Server 的 `/api/conversations` POST 返回 500，已创建的沙箱是否会被清理？是否存在沙箱泄漏？

### 3.13 Docker 沙箱的 `get_sandbox_by_session_api_key` 性能问题

**位置：** `docker_sandbox_service.py`

```python
async def get_sandbox_by_session_api_key(self, session_api_key):
    all_containers = self.docker_client.containers.list(all=True)
    for container in all_containers:
        env_vars = self._get_container_env_vars(container)
        if env_vars.get(SESSION_API_KEY_VARIABLE) == session_api_key:
            return await self._container_to_checked_sandbox_info(container)
```

**问题：**
- 列出所有容器后逐个检查环境变量，O(N) 复杂度
- 每次调用都读取所有容器的完整环境变量
- 在沙箱数量较多时性能显著下降
- Docker API 的同步调用进一步加剧延迟

**学习问题：**
85. 为什么不使用 Docker Label 存储session_api_key？Label 支持过滤查询（`filters={'label': ...}`），可避免全量扫描。
86. Process 沙箱和 Remote 沙箱如何实现 session_api_key 查找？它们的方案是否更高效？

### 3.14 环境变量注入的命名不一致

**位置：** 多处

- `OH_SESSION_API_KEYS_0`（索引式命名）
- `OH_WEBHOOKS_0_BASE_URL`（索引式 + 属性式）
- `OH_ALLOW_CORS_ORIGINS_0`（索引式）
- `SANDBOX_HOST_PORT`（无前缀）
- `RUNTIME`（无前缀，无命名空间）

**问题：**
- 有的用 `OH_` 前缀，有的无前缀
- 有的用索引式（`_0`），有的不用
- Agent Server 的环境变量注入逻辑（`env_parser.from_env`）依赖这种索引式命名，但缺乏文档

**学习问题：**
87. `env_parser.from_env` 如何解析索引式环境变量（如 `OH_SESSION_API_KEYS_0`、`OH_SESSION_API_KEYS_1`）？这种约定是否有正式规范？
88. 如何统一环境变量命名约定？迁移时如何保证向后兼容？

### 3.15 ACP Agent 的 Secret 注入兼容性问题

**位置：** `live_status_app_conversation_service.py` `_build_acp_start_conversation_request()`

```python
_sdk_supports_acp_secrets = (
    AgentContext.model_fields.get('secrets') is not None
    and isinstance(AgentContext.model_fields['secrets'].json_schema_extra, dict)
    and AgentContext.model_fields['secrets'].json_schema_extra.get('acp_compatible') is True
)
```

**问题：**
- 运行时反射检查 SDK 是否支持 ACP secrets，而非声明式配置
- 如果 SDK 升级后移除 `acp_compatible` 标记，此检查会静默失败
- `TODO` 注释表明这是临时方案，但临时方案容易成为永久方案

**学习问题：**
89. 特性检测（Feature Flag）与版本号检测各有什么优缺点？`_sdk_supports_acp_secrets` 属于哪种？
90. 如何将这种运行时反射检测替换为更可靠的机制（如 SDK 版本协商协议）？

---

## 四、架构级学习问题

### 4.1 进程间通信

50. App Server 与 Agent Server 之间的通信协议是什么？为什么选择 HTTP 而非 gRPC 或消息队列？
51. Agent Server 运行在沙箱内部，如何保证 App Server 能可靠地访问到它？网络断连时如何处理？
52. WebSocket 事件推送的完整链路是什么？从 Agent 工具调用到前端 UI 更新经过哪些组件？

### 4.2 可扩展性

53. 如何支持水平扩展 App Server？哪些状态是本地的（阻碍扩展），哪些是共享的？
54. 如果要将沙箱从 Docker 迁移到 Firecracker microVM，需要修改哪些抽象层？
55. Enterprise 模块通过什么机制扩展 OSS 功能？动态导入的工作原理是什么？

### 4.3 安全模型

56. `session_api_key` 的生成、验证和生命周期管理是什么？它如何防止沙箱逃逸？
57. JWT Token 的 `access_token_hard_timeout` 与 `conversation_max_age_seconds` 是什么关系？
58. Confirmation Mode（确认模式）的安全分析器（LLM Security Analyzer）如何决定哪些操作需要用户确认？

### 4.4 可观测性

59. LLM 调用的追踪（`litellm_extra_body.metadata`）包含哪些字段？如何在 SaaS 模式下聚合分析？
60. 事件回调的 Webhook 机制如何保证可靠投递？失败重试策略是什么？
61. PostHog 分析在 OSS 和 SaaS 模式下的数据收集范围有何不同？

### 4.5 数据一致性

62. 会话信息同时存储在数据库（`SQLAppConversationInfoService`）和 Agent Server 内存中，如何保证一致性？
63. 沙箱状态（`SandboxStatus`）的真相源是什么？App Server 如何检测到沙箱状态变化？
64. 用户设置的保存是乐观的还是悲观的？并发修改时如何处理？

### 4.6 数据库迁移与版本管理

65. App Server 使用 Alembic 管理数据库迁移（`app_lifespan/alembic/`），但迁移文件是简单的序号命名（001-009）。Enterprise 模块也有独立的 Alembic 迁移。两套迁移系统如何协调？当 OSS 和 Enterprise 使用同一数据库时，迁移顺序如何保证？
66. `AppLifespanService` 在应用启动时执行迁移。如果迁移失败，应用是否拒绝启动？如何在零停机部署中处理迁移？

### 4.7 多租户隔离

67. 事件存储的 `user_id` 前缀路径实现了文件系统级隔离。但 `SQLAppConversationInfoService` 的数据库查询是否有 `user_id` 过滤？如何防止用户 A 访问用户 B 的会话？
68. `SandboxService.search_sandboxes()` 返回所有沙箱，`_find_running_sandbox_for_user()` 通过 `sandbox.created_by_user_id == user_id` 过滤。但如果 `created_by_user_id` 为 None（Docker 沙箱的情况），如何保证隔离？

### 4.8 沙箱资源限制

69. Docker 沙箱的 `max_num_sandboxes` 限制通过 `pause_old_sandboxes()` 实现。被暂停的沙箱如何恢复？`pause_old_sandboxes()` 的 LRU 策略是什么？
70. Remote 沙箱的资源限制由谁管理？App Server 还是远程运行时服务？
71. 沙箱的 CPU/内存资源限制如何配置？`SandboxSpecInfo` 中没有资源字段。

### 4.9 Webhook 回调的可靠性

72. Agent Server 的 Webhook 回调通过 `OH_WEBHOOKS_0_BASE_URL` 配置。如果 App Server 重启，Agent Server 缓存的回调 URL 是否失效？
73. `EventCallbackService` 的回调是异步的。如果回调处理失败（如 Webhook 目标不可达），事件是否丢失？有无死信队列？

### 4.10 国际化与本地化

74. 前端使用 `i18next` + `react-i18next` 实现国际化。翻译文件如何同步后端的错误消息？后端返回的错误消息是否也支持国际化？
75. `npm run make-i18n` 生成的声明文件与实际翻译文件的同步机制是什么？

---

## 五、京东云 Qwen 35B 本地运行配置指南

### 5.1 前置条件

- Python 3.12+
- Node.js 22+
- Docker Desktop
- Poetry

### 5.2 配置步骤

#### 方式一：通过 config.toml 配置（适用于 CLI/Headless 模式）

创建 `config.toml` 文件：

```toml
[core]
workspace_base = "./workspace"
runtime = "docker"

[llm]
model = "openai/qwen-plus-35b"          # litellm 格式：provider/model
api_key = "你的京东云API Key"
base_url = "你的京东云API URL"            # 如 https://api.jdcloud.com/v1
```

#### 方式二：通过 Web UI 配置（推荐）

1. 启动应用：`make build && make run`
2. 在 Settings UI 中配置：
   - **Model**: 输入 `openai/qwen-plus-35b`（litellm 的 OpenAI 兼容格式）
   - **API Key**: 输入你的京东云 API Key
   - **Base URL**: 输入你的京东云 API URL

#### 关键说明

OpenHands 通过 litellm 库支持 OpenAI 兼容的 API。京东云 Qwen 35B 如果提供 OpenAI 兼容接口，需要：

1. **模型名称格式**：使用 `openai/模型名` 前缀，让 litellm 识别为 OpenAI 兼容提供者
2. **Base URL**：填写京东云的 API endpoint（需包含 `/v1` 路径，如果京东云的 URL 格式是 `https://xxx.com/v1`）
3. **API Key**：直接填入京东云提供的 API Key

> **注意**：Qwen 35B 的代码能力可能不如 Claude/GPT-4 级别模型，建议降低 `max_iterations` 并开启 `enable_history_truncation` 以避免上下文溢出。

### 5.3 运行命令

```bash
# 构建
make build

# 运行（同时启动前后端）
make run

# 或分别启动
make start-backend   # 后端端口 3000
make start-frontend  # 前端端口 3001
```

### 5.4 无 Docker 模式（可选）

如果不想使用 Docker 沙箱：
```bash
export INSTALL_DOCKER=0
export RUNTIME=local
make build && make run
```

---

## 六、学习路径建议

### 阶段一：理解架构（第 1-2 天）
- 阅读问题 1-9，理解核心数据流
- 运行项目，观察一次完整的会话启动

### 阶段二：深入核心（第 3-5 天）
- 阅读问题 10-30，理解各子系统的设计
- 修改配置，观察不同 Condenser 和 Sandbox 策略的行为

### 阶段三：深入进阶设计（第 6-7 天）
- 阅读问题 65-80，理解异步编排、ACP 双轨、Plugin 等进阶设计
- 尝试添加一个自定义 MCP 代理或 Plugin

### 阶段四：发现缺陷（第 8-9 天）
- 阅读问题 31-49 + 81-90，理解设计缺陷的根因
- 尝试修复一个设计缺陷，感受代码耦合度

### 阶段五：系统思维（第 10-12 天）
- 阅读问题 50-75，建立全局视角
- 思考如何将该项目的设计模式应用到自己的项目中
