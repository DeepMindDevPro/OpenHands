# OpenHands 核心架构文档

> 基于源码深度阅读整理，聚焦最核心的功能模块和架构流程

---

# 一、项目核心定位

OpenHands 是一个 **AI Agent 平台**，核心能力是：

1. **对话管理** — 用户与 AI Agent 进行代码相关的对话
2. **事件驱动** — 通过回调/Webhook 实现 Agent 行为的扩展和监控

**双体架构**：

```
┌─────────────────────────────────────────────────────────┐
│                    App Server (FastAPI)                   │
│              管理层：对话、用户、事件、API                  │
└──────────────────────────┬──────────────────────────────┘
                           │ HTTP
┌──────────────────────────▼──────────────────────────────┐
│                   Agent Server (SDK)                      │
│          执行层：LLM 调用、工具执行、事件生成              │
└─────────────────────────────────────────────────────────┘
```

- **App Server**：`openhands/app_server/` — 管理、编排、API 网关
- **Agent Server**：`openhands/sdk/` — AI Agent 运行时（LLM + 工具 + 事件）

---

# 二、系统总架构图

```
                              用户/前端
                                 │
                                 ▼
                      ┌─────────────────────┐
                      │  FastAPI App Server  │
                      └────────┬────────────┘
               ┌───────────────┼───────────────┐
               │               │               │
               ▼               ▼               ▼
     ┌─────────────┐  ┌──────────────┐  ┌──────────────┐
     │  Conversation │  │   Settings    │  │   Webhook    │
     │    Router     │  │    Router     │  │   Router     │
     └──────┬──────┘  └──────┬───────┘  └──────┬───────┘
            │                │                  │
            ▼                ▼                  ▼
  ┌──────────────────┐  ┌──────────┐   ┌──────────────────┐
  │  LiveStatusApp   │  │ Settings │   │ EventCallback    │
  │ ConversationSvc  │  │  Service │   │    Service       │
  └──┬───────┬───────┘  └──────────┘   └────────┬─────────┘
     │       │                                   │
     ▼       ▼                                   ▼
  ┌──────┐ ┌───────────────────┐    ┌─────────────────────┐
  │ SQL  │ │ EventCallbackSvc  │    │  EventCallback       │
  │ Info │ │ SkillLoader       │    │  Processors          │
  │ Svc  │ │ HookLoader        │    │  (SetTitle/Webhook)  │
  └──────┘ └───────────────────┘    └─────────────────────┘
```

---

# 三、核心模块详解

## 3.1 应用启动流程

```
uvicorn 启动
    │
    ▼
FastAPI 实例化
    │
    ├──► combine_lifespans ──► MCP Server Lifespan
    │                    └──► AppLifespanService
    │
    ├──► config_from_env ──► 解析 OH_ 环境变量
    │                   └──► 初始化所有 Injector
    │                        ├── DbSessionInjector
    │                        ├── EventServiceInjector
    │                        ├── EventCallbackServiceInjector
    │                        ├── JwtServiceInjector
    │                        └── HttpxClientInjector
    │
    ├──► 注册全局异常处理（AuthenticationError → 401）
    │
    ├──► 注册路由
    │    ├── v1_router
    │    ├── health_router
    │    └── Mount /mcp
    │
    └──► 注册中间件
         ├── LocalhostCORSMiddleware
         ├── CacheControlMiddleware
         └── RateLimitMiddleware
```

**关键文件**：
- 入口：`openhands/app_server/app.py`
- 配置：`openhands/app_server/config.py`

**启动过程**：
1. 初始化 Tavily MCP 代理
2. 创建 FastAPI 实例，组合多个 lifespan
3. 从环境变量解析 `AppServerConfig`，初始化所有依赖注入器
4. 注册全局异常处理器
5. 注册路由和中间件

---

## 3.2 对话管理 — 最核心的流程

### 3.2.1 对话启动流程（最重要的流程）

```
POST /app-conversations
    │
    ▼
创建 AppConversationStartTask  ──► Status: WORKING
    │
    ▼
有父对话？ ──是──► 继承父对话配置
    │否
    ▼
应用 SuggestedTask
    │
    ▼
等待沙箱启动  ──► Status: WAITING_FOR_SANDBOX
    │
    ▼
沙箱就绪？ ──否──► 轮询沙箱状态 ──┐
    │是                            │
    ▼                              │
克隆仓库  ──► Status: PREPARING_REPOSITORY
    │
    ▼
运行 .openhands/setup.sh  ──► Status: RUNNING_SETUP_SCRIPT
    │
    ▼
设置 Git Hooks  ──► Status: SETTING_UP_GIT_HOOKS
    │
    ▼
加载 Skills  ──► Status: SETTING_UP_SKILLS
    │
    ▼
构建 StartConversationRequest
    │
    ▼
HTTP POST → Agent Server  ──► Status: STARTING_CONVERSATION
    │
    ▼
保存 AppConversationInfo 到数据库
    │
    ▼
设置 EventCallback（SetTitleCallbackProcessor 等）
    │
    ▼
处理 Pending Messages（对话就绪前的排队消息）
    │
    ▼
Status: READY
```

**状态完整流转**：
```
WORKING → WAITING_FOR_SANDBOX → PREPARING_REPOSITORY
→ RUNNING_SETUP_SCRIPT → SETTING_UP_GIT_HOOKS
→ SETTING_UP_SKILLS → STARTING_CONVERSATION → READY（或任意阶段 ERROR）
```

**关键文件**：
- 路由：`openhands/app_server/app_conversation/app_conversation_router.py`
- 核心服务：`openhands/app_server/app_conversation/live_status_app_conversation_service.py`
- 数据模型：`openhands/app_server/app_conversation/app_conversation_models.py`

### 3.2.2 对话查询流程

```
GET /app-conversations/search
    │
    ▼
SQL 查询 AppConversationInfo（持久化元数据）
    │
    ▼
批量获取关联的 SandboxInfo
    │
    ▼
沙箱运行中？ ──否──► 使用存储状态
    │是
    ▼
HTTP GET → Agent Server 获取实时状态
    │
    ▼
合并 存储数据 + 实时状态
    │
    ▼
返回 AppConversationPage
```

**核心设计**：`LiveStatusAppConversationService` 采用 **存储数据 + 实时状态** 双源合并策略：
- 存储数据（SQL）：对话 ID、标题、创建时间等持久化信息
- 实时状态（Agent Server）：Agent 执行状态、token 消耗等运行时信息

---

## 3.3 依赖注入系统 — 贯穿全局的架构模式

```
AppServerConfig（配置中心）
    │
    ├── DbSessionInjector
    ├── EventServiceInjector
    ├── EventCallbackServiceInjector
    ├── JwtServiceInjector
    └── HttpxClientInjector
         │
         │  depends() 注入到路由
         ▼
┌──────────────────────────────────────────┐
│           路由函数                         │
│  async def start_conversation(            │
│      db: AsyncSession = db_dep,      ◄── 自动注入
│      jwt: JwtService = jwt_dep,     ◄── 自动注入
│      client: httpx.AsyncClient = ...,◄── 自动注入
│  ):                                       │
└──────────────────────────────────────────┘

注入生命周期：
  HTTP 请求进入 ──► inject(): 创建资源
                ──► yield: 提供资源给路由
                ──► 清理资源: 关闭连接/提交事务
```

**核心机制**：
```python
class Injector(Generic[T], ABC):
    @abstractmethod
    async def inject(self, state, request) -> AsyncGenerator[T, None]:
        yield resource        # 提供 → 使用 → 清理

    async def depends(self, request) -> AsyncGenerator[T, None]:
        # FastAPI 依赖注入入口
        async for result in self.inject(request.state, request):
            yield result
```

**配置选择实现**（`config_from_env` 根据环境变量自动选择）：
```python
if os.getenv('RUNTIME') == 'remote':
    config.sandbox = RemoteSandboxServiceInjector(...)
elif os.getenv('RUNTIME') == 'local':
    config.sandbox = ProcessSandboxServiceInjector()
else:
    config.sandbox = DockerSandboxServiceInjector(...)
```

---

## 3.4 事件系统 — 回调驱动的扩展机制

```
Agent Server 产生 Event
    │
    ├──► EventService 存储事件（Filesystem / S3 / GCS）
    │
    └──► 触发 EventCallback
              │
              ▼
     EventCallbackProcessor（多态分发）
         │
         ├── SetTitleCallbackProcessor  ──► 自动设置对话标题
         ├── WebhookCallbackProcessor   ──► 转发到外部 Webhook
         └── LoggingCallbackProcessor   ──► 记录日志

Webhook Router 接收 Agent 事件：
    │
    ▼
加载对话关联的 Callbacks
    │
    ▼
执行所有 Processor
    │
    ▼
更新 Callback 状态
```

**EventCallbackProcessor 多态**：
```python
class EventCallbackProcessor(DiscriminatedUnionMixin, ABC):
    @abstractmethod
    async def __call__(self, conversation_id, callback, event):
        """处理事件"""
```

**存储实现**：
| 组件 | 实现 | 说明 |
|------|------|------|
| 事件存储 | `FilesystemEventService` | 本地文件系统 |
| 事件存储 | `AwsEventService` | AWS S3 |
| 事件存储 | `GoogleCloudEventService` | GCP Storage |
| 回调存储 | `SQLEventCallbackService` | PostgreSQL |

---

## 3.5 MCP 集成 — Model Context Protocol

```
/mcp 端点
    │
    ▼
FastMCP Server
    │
    ├──► Tavily Search Proxy ──► Tavily Search API
    │
    └──► Git Provider Tools
              │
              ├── get_repositories
              ├── get_pull_requests
              └── get_branches
```

**MCP 的作用**：为 Agent Server 中的 AI Agent 提供工具调用能力，Agent 通过 MCP 协议访问搜索和仓库操作。

---

## 3.6 用户与认证

```
HTTP 请求
    │
    ▼
认证中间件
    │
    ├──► get_user_id: 从 Cookie/Token 提取用户 ID
    ├──► get_provider_tokens: 获取 Git Provider Token
    └──► get_access_token: 获取访问令牌
              │
              ▼
        UserContext 注入到路由
              │
              ├──► get_user_info: 获取用户设置
              └──► get_user_org: 获取组织信息
```

**UserContext 注入示例**：
```python
@router.post('')
async def start_conversation(
    user_context: UserContext = user_context_dependency,  # 自动注入
):
    user_id = await user_context.get_user_id()
    user_info = await user_context.get_user_info()
```

---

# 四、数据流全景图

```
┌──────────┐  ┌──────────┐  ┌───────────────┐
│  浏览器    │  │ API 客户端│  │ 外部 Webhook  │
└─────┬────┘  └────┬─────┘  └───────┬───────┘
      │            │                │
      │ WebSocket  │    REST        │ POST /webhook
      │   /REST    │                │
      ▼            ▼                ▼
┌─────────────────────────────────────────────┐
│              FastAPI Routers                 │
├─────────────────────────────────────────────┤
│  Conversation │ Settings │ Webhook │ MCP    │
│    Service    │ Service  │ Router  │ Router  │
├───────────────┴──────────┴─────────┴────────┤
│                                             │
│              App Server 内部服务              │
│                                             │
├──────────────┬───────────────┬──────────────┤
│   PostgreSQL │  File Store   │   S3 / GCS   │
└──────────────┴───────────────┴──────────────┘
                     │
                     │ HTTP
                     ▼
┌─────────────────────────────────────────────┐
│           Agent Server (Docker 容器)         │
├─────────────────────────────────────────────┤
│  LLM API 调用  │  工具执行  │  事件生成      │
└─────────────────────────────────────────────┘
```

---

# 五、核心模块清单

| 模块 | 路径 | 职责 |
|------|------|------|
| 应用入口 | `app_server/app.py` | FastAPI 实例、路由注册、中间件 |
| 全局配置 | `app_server/config.py` | 环境变量解析、DI 注入器配置 |
| 对话路由 | `app_server/app_conversation/app_conversation_router.py` | 对话 CRUD API |
| 对话服务 | `app_server/app_conversation/live_status_app_conversation_service.py` | 对话生命周期管理 |
| 对话信息 | `app_server/app_conversation/sql_app_conversation_info_service.py` | 对话元数据持久化 |
| 事件存储 | `app_server/event/filesystem_event_service.py` | 事件文件存储 |
| 事件回调 | `app_server/event_callback/sql_event_callback_service.py` | 回调持久化 |
| Webhook | `app_server/event_callback/webhook_router.py` | 外部事件推送 |
| MCP 服务 | `app_server/mcp/mcp_router.py` | MCP 工具协议 |
| 依赖注入 | `app_server/services/injector.py` | DI 基础框架 |
| JWT 服务 | `app_server/services/jwt_service.py` | 令牌签发/验证 |
| 数据库会话 | `app_server/services/db_session_injector.py` | SQLAlchemy 异步会话 |
| 用户上下文 | `app_server/user/user_context.py` | 用户信息注入 |
| 日志 | `app_server/utils/logger.py` | 自定义日志格式化 |
| 中间件 | `app_server/middleware.py` | CORS/缓存/限流 |
| Skill 加载 | `app_server/app_conversation/skill_loader.py` | Agent 技能加载 |
| Hook 加载 | `app_server/app_conversation/hook_loader.py` | Agent 钩子加载 |
| 消息队列 | `app_server/pending_messages/pending_message_service.py` | 待处理消息 |
| 动态导入 | `app_server/utils/import_utils.py` | 运行时实现替换 |

---

# 六、关键设计决策

## 6.1 App Server vs Agent Server 分离

```
App Server (管理层)              Agent Server (执行层)
├── 用户认证                        ├── LLM 调用
├── 对话 CRUD                       ├── 工具执行
├── 数据持久化                      ├── 事件生成
├── 事件回调管理                    ├── 状态管理
└── API 网关                        └── 对话循环
```

**好处**：
- App Server 可以管理多个 Agent Server
- Agent Server 崩溃不影响 App Server
- 可以独立扩展/部署

## 6.2 Injector 依赖注入

所有服务通过 `Injector[T]` 泛型基类管理生命周期：
- 创建资源 → `yield` 提供给路由 → 请求结束后自动清理
- 类似 Spring 的 `@RequestScope` Bean
- 支持运行时替换实现（`get_impl()` 动态导入）

## 6.3 DiscriminatedUnion 多态序列化

`EventCallbackProcessor` 使用 `DiscriminatedUnionMixin` 实现多态反序列化：
- 数据库中存储 processor 类型标识
- 读取时根据标识自动选择对应子类
- 类似 Jackson 的 `@JsonTypeInfo`

---

*本文档基于 OpenHands 项目源码深度阅读整理，所有流程图和架构描述均来自代码实际实现。*
