# OpenHands Tool 执行链路图

## 1. MCP 工具完整执行链路

```mermaid
graph TB
    subgraph "Client Layer"
        A[Agent/Sandbox] -->|MCP Request| B[MCP Client]
    end

    subgraph "Communication Layer"
        B -->|HTTP POST| C[FastAPI /mcp Endpoint]
    end

    subgraph "Application Server"
        C -->|Route Request| D[MCP Router]
        D -->|Authentication| E[Auth Service]
        E -->|Tokens| F[Session Context]
        D -->|Tool Dispatch| G[Tool Dispatcher]
    end

    subgraph "Service Layer"
        G -->|GitHub| H[GithubService]
        G -->|GitLab| I[GitLabService]
        G -->|Bitbucket| J[BitbucketService]
        G -->|Azure DevOps| K[AzureDevOpsService]
    end

    subgraph "External Services"
        H -->|API| L[GitHub API]
        I -->|API| M[GitLab API]
        J -->|API| N[Bitbucket API]
        K -->|API| O[Azure DevOps API]
    end

    L -->|Response| H
    M -->|Response| I
    N -->|Response| J
    O -->|Response| K

    H -->|Result| G
    I -->|Result| G
    J -->|Result| G
    K -->|Result| G

    G -->|Return| D
    D -->|Response| B
    B -->|Result| A

    style A fill:#e1f5ff
    style B fill:#fff3e0
    style C fill:#f3e5f5
    style D fill:#e8f5e9
    style G fill:#ffebee
    style H fill:#fff9c4
    style I fill:#fff9c4
    style J fill:#fff9c4
    style K fill:#fff9c4
```

## 2. Skills/Microagents 执行链路

```mermaid
graph LR
    subgraph "User/Agent Interaction"
        A[User Query] -->|Keywords| B[Skills Loader]
    end

    subgraph "Knowledge Retrieval"
        B -->|File System| C[skills/ Directory]
        B -->|Repository| D[.openhands/skills/]
        C -->|Parse| E[YAML Parser]
        D -->|Parse| E
        E -->|Extract| F[Knowledge Agents]
        E -->|Extract| G[Repository Agents]
    end

    subgraph "Context Assembly"
        F -->|Trigger| H[Context Builder]
        G -->|Trigger| H
        H -->|Inject| I[LLM Context]
    end

    subgraph "LLM Processing"
        I -->|Prompt| J[LLM]
        J -->|Response| K[Knowledge Application]
    end

    style A fill:#e1f5ff
    style B fill:#fff3e0
    style C fill:#f3e5f5
    style F fill:#e8f5e9
    style J fill:#ffebee
```

## 3. 详细的 MCP 工具调用序列图

```mermaid
sequenceDiagram
    participant Agent as Agent/Sandbox
    participant MCPClient as MCP Client
    participant FastAPI as FastAPI /mcp
    participant Router as MCP Router
    participant Auth as Auth Service
    participant Tool as Tool Function
    participant Service as Git Service
    participant External as External API

    Agent->>MCPClient: Call tool: create_pr()
    MCPClient->>FastAPI: POST /mcp (MCP Protocol)
    Note over MCPClient,FastAPI: Headers:<br/>X-OpenHands-ServerConversation-ID<br/>X-Session-API-Key
    FastAPI->>Router: Route to MCP Router
    Router->>Auth: Validate session
    Auth-->>Router: Access tokens & User ID
    Router->>Tool: Dispatch tool call
    Tool->>Tool: Parse parameters
    Tool->>Service: Call service method
    Service->>External: HTTP request to Git API
    Note over Service,External: Use OAuth/API Key
    External-->>Service: API Response
    Service-->>Tool: Result string
    Tool-->>Router: Tool execution result
    Router-->>FastAPI: Return response
    FastAPI-->>MCPClient: JSON Response
    MCPClient-->>Agent: Tool result
```

## 4. 配置与初始化流程

```mermaid
graph TD
    subgraph "Application Startup"
        A[FastAPI App Start] --> B[Initialize MCP Server]
        B --> C[Load Tool Definitions]
        C --> D[Register Tools with Router]
    end

    subgraph "Conversation Start"
        E[Create Conversation] --> F[Get User Settings]
        F --> G[Extract MCP Config]
        G --> H[Generate MCP URL]
        H --> I[Set HTTP Headers]
    end

    subgraph "Tool Configuration"
        J[MCP Client] --> K[Configure Server]
        K --> L[Set URL & Headers]
        L --> M[Ready to Call Tools]
    end

    D -.->|Expose| N[/mcp Endpoint]
    I -->|Pass to| J
    N -.->|Available to| J

    style A fill:#e1f5ff
    style E fill:#fff3e0
    style J fill:#f3e5f5
```

## 5. 关键组件关系图

```mermaid
graph LR
    subgraph "Core Components"
        A[FastMCP Server]
        B[MCP Router]
        C[MCP Client]
    end

    subgraph "Service Layer"
        D[GithubService]
        E[GitLabService]
        F[BitbucketService]
        G[AzureDevOpsService]
    end

    subgraph "Supporting Systems"
        H[Auth Service]
        I[Session Manager]
        J[Settings Store]
    end

    subgraph "External Systems"
        K[Git APIs]
        L[Tavily API]
    end

    A -->|Defines| B
    A -->|Exposes| M[/mcp Endpoint]
    C -->|Connects| M
    B -->|Uses| D
    B -->|Uses| E
    B -->|Uses| F
    B -->|Uses| G
    B -->|Calls| H
    B -->|Calls| I
    H -->|Gets| J
    D -->|Calls| K
    E -->|Calls| K
    F -->|Calls| K
    G -->|Calls| K

    style A fill:#e1f5ff
    style B fill:#fff3e0
    style M fill:#f3e5f5
    style H fill:#e8f5e9
    style K fill:#ffebee
```

## 6. 数据流与认证流程

```mermaid
flowchart TB
    subgraph "Authentication Flow"
        A1[User Login] --> A2[Session Created]
        A2 --> A3[Generate API Key]
        A3 --> A4[Store Session]
    end

    subgraph "Tool Request Flow"
        B1[Agent Request] --> B2[MCP Client]
        B2 --> B3[Attach Headers]
        B3 --> B4[Send to Server]
    end

    subgraph "Authorization"
        C1[Extract Headers] --> C2[Validate API Key]
        C2 --> C3[Get User Tokens]
        C3 --> C4[Map Provider Tokens]
    end

    subgraph "Tool Execution"
        D1[Select Tool] --> D2[Build Request]
        D2 --> D3[Call External API]
        D3 --> D4[Parse Response]
        D4 --> D5[Return Result]
    end

    A1 -->|User Context| B1
    B4 -->|Request| C1
    C4 -->|Tokens| D2
    D5 -->|Response| B1

    style A1 fill:#e1f5ff
    style C1 fill:#fff3e0
    style D1 fill:#f3e5f5
```

## 7. 文件与模块依赖关系

```mermaid
graph TD
    subgraph "Main Files"
        A1[mcp_router.py]
        A2[app_conversation.py]
        A3[settings.py]
    end

    subgraph "Service Layer"
        B1[github.py]
        B2[gitlab.py]
        B3[bitbucket.py]
        B4[azure_devops.py]
    end

    subgraph "Configuration"
        C1[mcp_config.py]
        C2[auth.py]
    end

    subgraph "Skills"
        D1[skills/ folder]
        D2[.openhands/skills/]
    end

    A1 -->|Uses| B1
    A1 -->|Uses| B2
    A1 -->|Uses| B3
    A1 -->|Uses| B4
    A1 -->|Loads| C1
    A1 -->|Uses| C2
    A1 -->|Integrates| D1
    A2 -->|Uses| D1

    style A1 fill:#e1f5ff
    style B1 fill:#fff3e0
    style D1 fill:#f3e5f5
```

## 8. 执行时间线与并发处理

```mermaid
gantt
    title MCP Tool 执行时间线
    dateFormat X
    axisFormat %s

    section 客户端层
    Agent 请求工具          :0, 10ms
    MCP Client 构建请求      :10, 15ms

    section 网络通信
    HTTP 请求传输           :25, 50ms
    MCP 协议序列化          :75, 30ms

    section 服务器层
    认证验证               :105, 20ms
    工具路由与分发          :125, 15ms

    section 服务层
    调用 Git 服务           :140, 500ms
    等待外部 API 响应        :140, 450ms

    section 响应处理
    解析响应              :590, 20ms
    返回给客户端           :610, 30ms

    section Skills 流程
    触发关键词检测         :0, 5ms
    加载相关技能           :5, 30ms
    注入上下文             :35, 15ms
```

## 关键说明

### 1. 认证与授权流程
- **会话 ID**: 通过 `X-OpenHands-ServerConversation-ID` 头传递
- **API 密钥**: 通过 `X-Session-API-Key` 头传递
- **Provider Tokens**: 通过 OAuth 或 API Key 获取，不直接暴露给沙箱

### 2. 安全性考虑
- MCP 协议提供安全通信
- API 密钥不直接暴露给 Agent
- 所有工具调用通过主应用服务器中转
- 支持请求审计和追踪

### 3. 性能优化
- 支持异步工具调用
- 外部 API 调用可并发
- 响应快速序列化
- 连接池管理

### 4. 扩展性
- 新增工具只需在 Router 添加新函数
- 支持自定义 MCP 服务器配置
- Skills 系统支持动态加载
