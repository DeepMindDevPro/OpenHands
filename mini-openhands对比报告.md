# mini-openhands VS openhands 核心功能差异对比报告

> 基于对 OpenHands 本地源码的深度阅读，精确对比 mini-openhands 能复现什么、不能覆盖什么。

---

## 一、总体规模对比

| 维度 | OpenHands 完整版 | mini-openhands | 覆盖率 |
|------|-----------------|----------------|--------|
| 总代码量 | ~200,000 行 | ~2,000 行 | 1% 代码量 |
| 核心模块代码 | ~42,652 行(SDK) | ~2,000 行 | ~5% 核心代码 |
| 外部依赖 | 60+ PyPI 包 | 3 个(litellm/pydantic/jinja2) | 极简 |
| 工具数量 | 11类30+工具 | 3个(Bash/FileEdit/Finish) | 核心3工具 |
| 运行环境 | Docker容器+K8s+PostgreSQL | 本地进程 | 零基础设施 |

---

## 二、6大核心特性逐项对比

### 🏆 1. Agent 执行循环

| 子特性 | OpenHands | mini-openhands | 能学会? |
|--------|-----------|----------------|---------|
| step() 8阶段循环 | ✅ 完整8阶段 | ✅ 简化5阶段（去掉pending_actions/Critic检查） | ✅ **核心循环逻辑完全掌握** |
| 异常处理链（3层） | ✅ FunctionCallValidation→反馈LLM, MalformedHistory→恢复压缩, ContextExceed→强制压缩 | ✅ 完整实现3层异常链 | ✅ **这是最值得学的部分，mini版完整复现** |
| Critic 迭代精化 | ✅ CriticBase打分+自动重试+max_iterations | ❌ 不实现 | ❌ 闭环反馈机制需读源码 |
| StuckDetector 5种检测 | ✅ 重复动作/重复错误/独白/交替/上下文溢出 | ⚠️ 仅实现"重复动作"检测 | ⚠️ 学到检测思路，5种模式需扩展 |
| Hook 阻塞检查 | ✅ UserPromptSubmit Hook可拦截/修改/阻止消息 | ❌ 不实现 | ❌ Hook拦截机制需读源码 |
| pending_actions 隐式确认 | ✅ 确认模式下自动确认pending actions | ❌ 不实现 | ❌ 安全确认流程需读源码 |

**能学会的：** Agent循环的核心骨架、LLM调用→工具执行→观察结果的主循环、三层异常恢复策略
**不能掌握的：** Critic闭环反馈、Hook拦截、安全确认流程

---

### 🏆 2. 工具系统

| 子特性 | OpenHands | mini-openhands | 能学会? |
|--------|-----------|----------------|---------|
| Action-Observation 统一协议 | ✅ 30+工具统一协议 | ✅ 3个工具统一协议 | ✅ **协议设计完全掌握** |
| DiscriminatedUnionMixin | ✅ kind字段自动多态序列化/反序列化 | ✅ 简化版实现（Pydantic model_validator） | ✅ **核心机制掌握，OpenHands用更复杂的元类实现** |
| ToolDefinition 泛型基类 | ✅ ToolDefinition[ActionT, ObservationT] | ✅ 简化泛型实现 | ✅ **设计模式掌握** |
| DeclaredResources 并发控制 | ✅ 完整ResourceLockManager+3种状态 | ✅ 简化版（asyncio.Lock+资源键映射） | ✅ **核心思想掌握** |
| ParallelToolExecutor | ✅ 基于ResourceLockManager的并发执行 | ✅ asyncio.gather+资源锁 | ✅ **并行执行模式掌握** |
| 工具注册表 Registry | ✅ _REG全局注册表+3种factory | ✅ 简化字典注册 | ✅ **注册模式掌握** |
| MCP 动态适配 | ✅ MCPToolDefinition从JSON Schema动态创建 | ❌ 不实现 | ❌ MCP协议集成需读源码 |
| security_risk/summary 注入 | ✅ 导出Schema时动态注入 | ✅ 简化版注入 | ✅ **安全增强模式掌握** |
| Browser 工具集 | ✅ 14个浏览器操作(Playwright) | ❌ 不实现 | ❌ 浏览器自动化需读源码 |
| TaskToolSet 子代理 | ✅ 启动子代理任务 | ❌ 不实现 | ❌ 多Agent编排需读源码 |
| ToolAnnotations | ✅ readOnlyHint/destructiveHint等MCP标注 | ❌ 不实现 | ❌ MCP标注体系需读源码 |
| 自动命名(__init_subclass__) | ✅ CamelCase→snake_case自动转换 | ✅ 简化版实现 | ✅ **元编程模式掌握** |
| create() 工厂方法 | ✅ 从ConversationState获取运行时参数 | ✅ 简化版 | ✅ **工厂模式掌握** |

**能学会的：** Action-Observation协议设计、工具注册与发现机制、声明式资源并发控制、工具定义与执行分离的架构模式
**不能掌握的：** MCP动态工具适配、浏览器自动化、子代理委托、MCP ToolAnnotations标注体系

---

### 🏆 3. Condenser 上下文压缩

| 子特性 | OpenHands | mini-openhands | 能学会? |
|--------|-----------|----------------|---------|
| CondenserBase 抽象 | ✅ 完整ABC | ✅ 完整ABC | ✅ **策略模式掌握** |
| NoopCondenser | ✅ 不压缩 | ✅ 实现 | ✅ |
| RecentCondenser | ✅ 保留最近N事件 | ✅ 实现 | ✅ **核心压缩逻辑掌握** |
| LLMSummarizingCondenser | ✅ LLM摘要+独立LLM配置 | ✅ 实现（无独立LLM配置） | ⚠️ 核心流程掌握，但独立LLM配置特性缺失 |
| AmortizedCondenser | ✅ 渐进遗忘+keep_first保护 | ❌ 不实现 | ❌ 渐进遗忘算法需读源码 |
| LLMAttentionCondenser | ✅ 注意力评分选择 | ❌ 不实现 | ❌ 注意力评分机制需读源码 |
| ObservationMaskingCondenser | ✅ 遮蔽旧观察 | ❌ 不实现 | ❌ 隐私保护压缩需读源码 |
| View 只读事件视图 | ✅ 过滤+原子性+匹配 | ⚠️ 简化版（仅过滤） | ⚠️ 基本概念掌握，Tool Loop Atomicity缺失 |
| 异常触发强制压缩 | ✅ ContextExceed→缩小窗口→再压缩 | ✅ 实现 | ✅ **容错设计掌握** |
| 策略可插拔 | ✅ 无需修改Agent即可切换 | ✅ 实现 | ✅ **开闭原则掌握** |
| 独立Condenser LLM | ✅ 可用更便宜模型做压缩 | ❌ 不实现 | ❌ 成本优化策略需读源码 |

**能学会的：** 策略模式的实际应用、上下文压缩的核心流程、异常触发的容错压缩路径
**不能掌握的：** 渐进遗忘算法、注意力评分选择、独立Condenser LLM的成本优化、View的Tool Loop Atomicity

---

### 🏆 4. 安全纵深防御

| 子特性 | OpenHands | mini-openhands | 能学会? |
|--------|-----------|----------------|---------|
| SecurityAnalyzerBase 抽象 | ✅ 完整ABC | ✅ 完整ABC | ✅ **策略模式掌握** |
| PatternSecurityAnalyzer | ✅ 正则匹配危险模式 | ✅ 实现基础正则 | ✅ **模式匹配思路掌握** |
| ConfirmationPolicy | ✅ NeverConfirm/ConfirmRisky/AlwaysConfirm | ✅ 实现三级策略 | ✅ **策略选择掌握** |
| EnsembleSecurityAnalyzer | ✅ 组合多分析器取最严 | ❌ 不实现 | ❌ fail-closed组合策略需读源码 |
| PolicyRailSecurityAnalyzer | ✅ 策略护栏 | ❌ 不实现 | ❌ 策略组合检测需读源码 |
| LLMSecurityAnalyzer | ✅ LLM判断风险 | ❌ 不实现 | ❌ LLM辅助安全判断需读源码 |
| security_risk 字段注入 | ✅ LLM预测+Schema注入 | ✅ 简化版注入 | ✅ **LLM参与安全评估的模式掌握** |
| fail-closed 设计 | ✅ 默认最严，有疑即阻 | ❌ 不实现 | ❌ 防御性设计哲学需读源码 |

**能学会的：** 安全分析的基本框架、正则模式匹配、ConfirmationPolicy三级策略、security_risk注入模式
**不能掌握的：** Ensemble fail-closed组合策略、PolicyRail策略护栏、LLM辅助安全判断、纵深防御的多层协同

---

### 🏆 5. Prompt 工程

| 子特性 | OpenHands | mini-openhands | 能学会? |
|--------|-----------|----------------|---------|
| SystemPromptEvent 组装 | ✅ 基础指令+工具Schema+动态上下文 | ✅ Jinja2模板+工具Schema | ✅ **动态组装模式掌握** |
| Skills 多源加载 | ✅ 5种来源+Agent Server代理 | ⚠️ 仅本地文件加载 | ⚠️ 基本概念掌握，多源合并策略缺失 |
| Skill KeywordTrigger | ✅ 关键词匹配触发 | ✅ 实现 | ✅ **触发机制掌握** |
| Skill TaskTrigger | ✅ 任务类型触发 | ❌ 不实现 | ❌ 任务触发需读源码 |
| Hook 拦截层 | ✅ UserPromptSubmit Hook | ❌ 不实现 | ❌ Hook拦截需读源码 |
| Plugin 参数注入 | ✅ 参数追加到initial_message | ❌ 不实现 | ❌ Plugin体系需读源码 |
| Planning vs Default模板 | ✅ 两套模板+工具集 | ⚠️ 仅Default模板 | ❌ 多Agent模板切换需读源码 |
| Skill 合并去重 | ✅ "后覆盖前"+名称去重 | ✅ 实现 | ✅ **合并策略掌握** |

**能学会的：** Jinja2模板动态组装、Skill加载与触发、Skill合并去重策略
**不能掌握的：** 5种Skill来源的多源加载架构、Hook拦截机制、Plugin参数注入、Planning Agent的模板切换

---

### 🏆 6. 事件驱动架构

| 子特性 | OpenHands | mini-openhands | 能学会? |
|--------|-----------|----------------|---------|
| Event 基类体系 | ✅ 完整层次（7种事件类型） | ✅ 5种核心事件 | ✅ **事件分类掌握** |
| EventStore 持久化 | ✅ FileSystem/S3/GCS多后端 | ✅ 内存列表存储 | ⚠️ 接口掌握，持久化后端缺失 |
| EventCallbackProcessor | ✅ DiscriminatedUnion多态分发 | ✅ 简化版多态分发 | ✅ **回调模式掌握** |
| 存储-回调分离 | ✅ EventService + EventCallbackService | ✅ 分离实现 | ✅ **解耦架构掌握** |
| 回调结果跟踪 | ✅ SUCCESS/FAILED/RETRY+错误分类 | ⚠️ 仅SUCCESS/FAILED | ⚠️ 基本概念掌握，重试机制缺失 |
| SetTitleCallbackProcessor | ✅ 自动提取对话标题 | ✅ 简化版实现 | ✅ **回调处理器模式掌握** |
| WebhookCallbackProcessor | ✅ 转发到外部Webhook | ❌ 不实现 | ❌ Webhook集成需读源码 |
| JWT认证 | ✅ JWE加密+多密钥轮换 | ❌ 不实现 | ❌ 安全认证需读源码 |
| 事件流式推送(SSE/WebSocket) | ✅ 实时推送到前端 | ❌ 不实现 | ❌ 实时事件流需读源码 |

**能学会的：** 事件分类体系、存储-回调分离架构、DiscriminatedUnion多态分发
**不能掌握的：** 多后端持久化、Webhook转发、JWT认证、实时事件流推送

---

## 三、完全不能覆盖的 OpenHands 模块

以下模块在 mini-openhands 中完全不涉及，必须通过阅读源码掌握：

| 模块 | 代码量 | 核心价值 | 为什么不能简化实现 |
|------|--------|----------|-------------------|
| **沙箱系统（Docker/Process/Remote）** | ~3,249行 | 代码执行的隔离与安全 | 依赖Docker SDK/K8s客户端，基础设施依赖 |
| **App Server（FastAPI）** | ~29,385行 | Web服务层、REST API、依赖注入 | 需要FastAPI+PostgreSQL+JWT全套 |
| **Enterprise 多租户** | ~105,476行 | SaaS认证/计费/组织管理 | 商业逻辑，非核心架构 |
| **前端（React）** | ~59,871行 | UI交互/实时事件流/WebSocket | 完全不同的技术栈 |
| **Git Provider 集成** | ~7,862行 | GitHub/GitLab/Bitbucket/Azure DevOps | 5套API适配，OAuth流程 |
| **ACP Agent** | - | Claude Code/Codex CLI 子进程管理 | 依赖外部Agent二进制 |
| **MCP Server 代理** | ~456行 | Tavily搜索代理/Git工具代理 | 依赖FastMCP服务端 |
| **LLM 双模式** | ~7,913行 | Completion API + Responses API | 仅实现Completion API |
| **LLMRouter 负载均衡** | - | 多模型Random/Multimodal路由 | 多模型管理场景 |

---

## 四、学习价值总结

### ✅ 通过 mini-openhands 能学会的（核心设计模式）

| 设计模式 | 对应 OpenHands 源码 | 掌握程度 |
|----------|-------------------|----------|
| **Agent 循环 + 异常恢复** | `sdk/agent/agent.py` step() | 深度掌握 |
| **Action-Observation 统一协议** | `sdk/tool/` ToolDefinition | 深度掌握 |
| **DiscriminatedUnion 多态序列化** | `sdk/utils/models.py` | 掌握核心思想 |
| **DeclaredResources 声明式并发** | `sdk/tool/` ParallelToolExecutor | 深度掌握 |
| **Strategy 策略模式（Condenser/Security）** | `sdk/context/` + `sdk/security/` | 深度掌握 |
| **Event-Callback 解耦** | `event/` + `event_callback/` | 掌握架构模式 |
| **Schema 安全增强（security_risk注入）** | `sdk/tool/tool.py` | 深度掌握 |
| **工具注册与发现** | `sdk/tool/registry.py` | 掌握 |
| **Jinja2 动态 Prompt 组装** | 系统提示模板体系 | 掌握 |

### ❌ 通过 mini-openhands 不能掌握的（需读源码）

| 缺失能力 | 对应源码位置 | 重要程度 | 建议 |
|----------|-------------|----------|------|
| **Critic 闭环反馈** | `sdk/agent/critic.py` | ⭐⭐⭐⭐ | 必读，质量提升的关键 |
| **Hook 拦截机制** | `sdk/hooks/` + `hook_loader.py` | ⭐⭐⭐⭐ | 必读，Agent行为控制的核心 |
| **MCP 动态工具适配** | `sdk/tool/mcp_tool.py` | ⭐⭐⭐⭐⭐ | 必读，工具生态扩展的关键 |
| **Ensemble fail-closed 安全** | `sdk/security/ensemble.py` | ⭐⭐⭐ | 选读，安全架构进阶 |
| **沙箱隔离体系** | `app_server/sandbox/` | ⭐⭐⭐⭐ | 必读，生产部署的关键 |
| **5种 Skill 多源加载** | `skill_loader.py` + Agent Server | ⭐⭐⭐ | 选读，理解5源合并策略 |
| **Planning Agent 模板切换** | `system_prompt_planning.j2` | ⭐⭐⭐ | 选读，多Agent模板设计 |
| **LLM 双API模式** | `sdk/llm/` | ⭐⭐ | 选读，OpenAI API演进 |
| **实时事件流（SSE/WebSocket）** | 前端WebSocket上下文 | ⭐⭐⭐ | 选读，实时交互架构 |
| **ACP Agent 子进程管理** | `live_status_app_conversation_service.py` | ⭐⭐ | 选读，外部Agent集成 |
| **Namespace Package 架构** | `openhands/__init__.py` | ⭐⭐⭐ | 选读，模块化设计 |
| **依赖注入体系** | `app_server/services/injector.py` + `config.py` | ⭐⭐⭐ | 选读，企业级DI设计 |

---

## 五、最优学习路径建议

### Phase 1：造 mini-openhands（1周）— 掌握核心设计模式

```
Day1-2: schema.py + event.py → 理解 DiscriminatedUnion + 事件体系
Day3-4: tool.py + tools/ → 理解 Action-Observation + DeclaredResources
Day5:   condenser.py → 理解策略模式 + 异常触发压缩
Day6:   agent.py + security.py → 理解核心循环 + 安全评估
Day7:   main.py + 端到端测试 → 跑通完整流程
```

### Phase 2：对照源码补盲区（3天）— 读取 mini 版缺失的关键模块

```
Day8:  读 sdk/agent/critic.py + sdk/hooks/ → 补 Critic闭环 + Hook拦截
Day9:  读 sdk/tool/mcp_tool.py + app_server/mcp/ → 补 MCP动态适配
Day10: 读 app_server/sandbox/ → 补 沙箱隔离体系
```

### Phase 3：架构级理解（2天）— 从全局视角理解完整系统

```
Day11: 读 app_server/config.py + services/injector.py → 理解15个Injector的DI体系
Day12: 读 live_status_app_conversation_service.py → 理解对话启动8状态 + 全链路串联
```

---

## 六、mini-openhands 的代码量预估

```
mini_openhands/
├── core/
│   ├── schema.py              # ~120行  DiscriminatedUnionMixin + Action/Observation基类
│   ├── event.py               # ~100行  Event体系5种类型 + 内存EventStore
│   └── condenser.py           # ~150行  CondenserBase + Noop/Recent/LLM三种策略
├── agent/
│   ├── agent.py               # ~180行  Agent.step() 5阶段循环 + 3层异常链
│   ├── conversation.py        # ~100行  ConversationState + LocalConversation.run()
│   └── stuck_detector.py      # ~60行   简化版重复动作检测
├── tools/
│   ├── tool_definition.py     # ~150行  ToolDefinition + DeclaredResources + Registry
│   ├── parallel_executor.py   # ~80行   ParallelToolExecutor + 资源锁
│   ├── terminal.py            # ~80行   TerminalTool（subprocess执行）
│   └── file_editor.py         # ~120行  FileEditorTool（view/str_replace/create）
├── security/
│   ├── analyzer.py            # ~80行   PatternSecurityAnalyzer + ConfirmationPolicy
│   └── risk.py                # ~40行   security_risk 注入
├── prompt/
│   ├── system_prompt.j2       # ~30行   系统提示模板
│   └── skill_loader.py        # ~80行   Skill加载 + KeywordTrigger
├── events/
│   ├── event_store.py         # ~50行   内存EventStore
│   └── callback.py            # ~80行   EventCallbackProcessor + SetTitleProcessor
├── llm/
│   └── llm.py                 # ~80行   litellm封装（Completion API）
└── main.py                    # ~80行   CLI入口 + 用户交互循环

合计: ~1,870行核心代码
```

### 依赖极简

```toml
[project]
dependencies = [
    "litellm",       # LLM统一接口（唯一重依赖）
    "pydantic>=2",   # 数据模型
    "jinja2",        # Prompt模板
]
```

---

---

## 六、mini-openhands 技术架构与功能模块

### 6.1 分层架构图

```
┌─────────────────────────────────────────────────────────────────┐
│                        交互层 CLI                                │
│                    main.py (CLI入口+用户交互循环)                 │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                         Agent 层                                │
│  ┌──────────────────┐ ┌──────────────────┐ ┌────────────────┐  │
│  │ agent.py         │ │ conversation.py  │ │ stuck_detector │  │
│  │ step() 5阶段循环  │ │ ConversationState│ │ StuckDetector  │  │
│  └──────────────────┘ └──────────────────┘ └────────────────┘  │
└──┬──────────┬──────────┬──────────┬──────────┬─────────────────┘
   │          │          │          │          │
   ▼          ▼          ▼          ▼          ▼
┌─────────┐┌─────────┐┌─────────┐┌─────────┐┌─────────────────┐
│Prompt层 ││ 安全层  ││上下文   ││ 工具层  ││    事件层       │
│         ││         ││管理层   ││         ││                 │
│system_  ││analyzer ││condenser││tool_def ││event_store      │
│prompt.j2││.py      ││.py     ││.py     ││.py (内存存储)   │
│         ││Pattern  ││         ││ToolDef  ││                 │
│skill_   ││Security ││Noop    ││Declared ││callback.py      │
│loader.py││+Policy  ││Recent  ││Resources││EventCallback    │
│         ││+risk    ││+LLM    ││+Registry││+SetTitle        │
│Keyword  ││注入     ││Condenser││+Parallel││                 │
│Trigger  ││         ││         ││Executor ││                 │
└────┬────┘└────┬────┘└────┬────┘└────┬────┘└────┬────────────┘
     │          │          │          │          │
     │          │          ▼          ▼          ▼
     │          │   ┌─────────────────────────────────────────┐
     │          │   │            基础协议层                    │
     │          │   │  schema.py: DiscriminatedUnionMixin     │
     │          │   │  Action基类 / Observation基类           │
     │          │   └─────────────────────────────────────────┘
     │          │
     ▼          ▼
┌─────────────────────────┐
│       LLM 层            │
│  llm.py (litellm封装)   │
└─────────────────────────┘
```

### 6.2 核心数据流图

```
用户CLI              main.py               Agent               Prompt组装            Condenser
  │                    │                    │                     │                     │
  │──输入指令──────────>│                    │                     │                     │
  │                    │──step(message)────>│                     │                     │
  │                    │                    │──组装Prompt────────>│                     │
  │                    │                    │<──完整prompt────────│                     │
  │                    │                    │──condense(history)──────────────────────>│
  │                    │                    │<──压缩后上下文───────────────────────────│
  │                    │                    │
  │                    │                    │              LLM(litellm)                               │
  │                    │                    │──completion(prompt+context)────>│                     │
  │                    │                    │<──LLM响应(Action/Message)──────│                     │
  │                    │                    │
  │                    │                    │           SecurityAnalyzer                              │
  │                    │                    │──security_check(action)────────>│                     │
  │                    │                    │<──风险评估结果──────────────────│                     │
  │                    │                    │
  │                    │                    │    ┌─安全通过/用户确认──┐                                  │
  │                    │                    │    │                    │──阻止执行──>生成拒绝Obs   │
  │                    │                    │    ▼                                                    │
  │                    │                    │  ToolExecutor         EventStore                        │
  │                    │                    │──execute(action)────>│                                 │
  │                    │                    │<──Observation结果────│                                 │
  │                    │                    │──store(event)─────────────────────────────────────────>│
  │                    │                    │                                                          │
  │                    │<──step结果─────────│                                                          │
  │<──输出结果─────────│                    │                                                          │
  │                    │                    │                                                          │
  │                    │                    │◄──── 循环直到 FinishAction 或 max_iterations ──────────►│
```

### 6.3 模块依赖关系图

```
  编排层                                  功能层                          基础设施层              独立层
┌─────────────────────┐    ┌─────────────────────────────┐    ┌──────────────────┐  ┌──────────────────┐
│ main.py             │    │ condenser.py                │    │ event.py         │  │ schema.py        │
│   │                 │    │   │                         │    │   │              │  │ Discriminated    │
│   ▼                 │    │   ▼                         │    │   ▼              │  │ UnionMixin      │
│ conversation.py     │───>│ security/                  │    │ Event体系        │─>│ Action基类       │
│   │                 │    │   │                         │    │                  │  │ Observation基类  │
│   ▼                 │    │   ▼                         │    │ llm.py           │  └──────────────────┘
│ agent.py            │───>│ prompt/ ──> tools/          │───>│ litellm封装      │
│                     │    │             │               │    └──────────────────┘
│                     │    │             ▼               │
│                     │    │         schema.py           │
└─────────────────────┘    └─────────────────────────────┘

依赖方向: 编排层 → 功能层 → 基础设施层 → 独立层
         agent.py 依赖: condenser, security, prompt, tools, llm, event
         tools/    依赖: schema (Action/Observation协议)
         event/    依赖: schema (Event基类)
         condenser 依赖: event (压缩Event列表)
```

### 6.4 功能模块详细说明

#### 模块1：基础协议层 — `core/schema.py` (~120行)

| 类/函数 | 核心职责 | 关键方法 | 数据流向 |
|---------|---------|---------|---------|
| `DiscriminatedUnionMixin` | kind字段多态序列化/反序列化 | `model_validator(mode='before')` 根据kind字段分发到对应子类 | 所有Action/Observation的序列化基础 |
| `Action`(基类) | 工具调用的统一抽象 | `kind: str` + `thought: str` | Agent→Tool的输入协议 |
| `Observation`(基类) | 工具执行结果的统一抽象 | `kind: str` + `content: str` + `error: bool` | Tool→Agent的输出协议 |
| `BashAction` | 终端命令执行请求 | `command: str` | Agent→TerminalTool |
| `BashObservation` | 终端命令执行结果 | `output: str` + `exit_code: int` | TerminalTool→Agent |
| `FileEditAction` | 文件编辑请求 | `path: str` + `command: str`(view/str_replace/create) | Agent→FileEditorTool |
| `FileEditObservation` | 文件编辑结果 | `content: str` + `diff: str` | FileEditorTool→Agent |
| `FinishAction` | 任务结束信号 | `message: str` | Agent→Conversation |
| `MessageAction` | 用户/Agent消息 | `content: str` + `role: str` | 用户→Agent / Agent→用户 |

#### 模块2：事件层 — `core/event.py` + `events/` (~230行)

| 类/函数 | 核心职责 | 关键方法 | 数据流向 |
|---------|---------|---------|---------|
| `Event`(基类) | 事件分类基础 | `kind: str` + `timestamp: datetime` | 所有事件的基类 |
| `ActionEvent` | 包装Action执行 | `action: Action` | Agent→EventStore |
| `ObservationEvent` | 包装Observation结果 | `observation: Observation` | Tool→EventStore |
| `MessageEvent` | 对话消息 | `content: str` + `role: str` | 用户/Agent→EventStore |
| `CondensationEvent` | 上下文压缩记录 | `summary: str` | Condenser→EventStore |
| `ErrorEvent` | 异常记录 | `error: str` + `source: str` | 异常处理→EventStore |
| `InMemoryEventStore` | 内存事件存储 | `append()` / `get_events()` / `filter_by_type()` | 事件持久化 |
| `EventCallbackProcessor` | 回调分发 | `process(event)` → 根据kind分发 | EventStore→Callback |
| `SetTitleCallbackProcessor` | 自动提取对话标题 | `process(event)` → 首条消息提取 | 事件→标题 |

#### 模块3：上下文管理 — `core/condenser.py` (~150行)

| 类/函数 | 核心职责 | 关键方法 | 数据流向 |
|---------|---------|---------|---------|
| `CondenserBase`(ABC) | 压缩策略抽象 | `condense(events: list[Event]) → list[Event]` | Agent→Condenser→压缩后事件 |
| `NoopCondenser` | 不压缩(直通) | `condense()` → 原样返回 | 调试模式 |
| `RecentCondenser` | 保留最近N事件 | `condense()` → 保留后N条 | 长对话裁剪 |
| `LLMSummarizingCondenser` | LLM摘要压缩 | `condense()` → 旧事件LLM摘要 + 新事件保留 | 智能压缩 |
| `create_condenser()` | 工厂方法 | 根据配置创建对应策略实例 | 配置→策略实例 |

**压缩策略选择逻辑：**
```
if 事件数 <= max_events:     → NoopCondenser（无需压缩）
elif 配置 == "recent":       → RecentCondenser（简单裁剪）
elif 配置 == "llm":          → LLMSummarizingCondenser（智能摘要）
```

**异常触发强制压缩路径（对应OpenHands的ContextExceed处理）：**
```
LLM调用失败(ContextLengthExceeded)
  → Condenser.condense() 缩小窗口
  → 重新组装prompt重试
  → 仍失败则 RecentCondenser 兜底
```

#### 模块4：Agent层 — `agent/` (~340行)

| 类/函数 | 核心职责 | 关键方法 | 数据流向 |
|---------|---------|---------|---------|
| `Agent` | 核心执行循环 | `step(message)` → 5阶段循环 | 主入口 |
| `ConversationState` | 对话状态管理 | `events: list` + `max_iterations: int` + `iteration: int` | Agent→状态容器 |
| `StuckDetector` | 卡住检测 | `is_stuck(events)` → bool | Agent→检测→中断决策 |

**Agent.step() 5阶段循环详解：**

```
step() 收到用户消息
    │
    ▼
┌─────────────────────────────────────────┐
│ 阶段1: 组装Prompt                        │
│   SystemPrompt + Context + Skills        │
└────────────────────┬────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────┐
│ 阶段2: 调用LLM                          │
│   litellm.completion()                  │
└────────────────────┬────────────────────┘
                     │
            ┌────────┴────────┐
            │  异常恢复链      │
            │                 │
            │ ①ContextLength  │
            │  Exceeded ──────┼──> 反馈LLM"输出过长请缩短" ──> 重试阶段2
            │                 │
            │ ②Malformed      │
            │  History ───────┼──> 强制压缩 Condenser.condense() ──> 重回阶段1
            │                 │
            │ ③ContextExceed ─┼──> 缩小窗口重试 RecentCondenser兜底 ──> 重回阶段1
            └────────┬────────┘
                     │ 正常返回
                     ▼
            ┌────────┴────────┐
            │ 阶段3: 解析响应  │
            │ Action or Message│
            └──┬──────────┬───┘
               │          │
         是Action    是Message
               │          │
               ▼          ▼
┌────────────────────┐   直接输出消息 ──> 返回最终结果
│ 阶段4: 安全检查     │
│ SecurityAnalyzer评估│
└────────┬───────────┘
         │
    ┌────┴────────────┐
    │ 风险评估?        │
    ├─ 安全 ──────────┼──> 进入阶段5
    ├─ 需确认 ────────┼──> 询问用户确认
    │                  │      ├─ 确认 ──> 进入阶段5
    │                  │      └─ 拒绝 ──> 生成拒绝Observation
    └──────────────────┘
         │
         ▼
┌─────────────────────────────────────────┐
│ 阶段5: 执行工具                          │
│   ToolExecutor.execute()                │
└────────────────────┬────────────────────┘
                     │
                     ▼
         存储Observation到EventStore
                     │
                     ▼
            ┌────────┴────────┐
            │ 是FinishAction?  │
            ├─ 否 ────────────┼──> 回到阶段2（继续循环）
            └─ 是 ────────────┘
                     │
                     ▼
              返回最终结果
```

**3层异常恢复链：**

| 异常 | 触发条件 | 恢复策略 | 对应源码 |
|------|---------|---------|---------|
| `FunctionCallValidation` | LLM输出非法工具调用 | 反馈错误信息给LLM重试 | `sdk/agent/agent.py` step() |
| `MalformedHistory` | 历史消息格式错误 | 强制压缩上下文后重试 | `sdk/agent/agent.py` step() |
| `ContextLengthExceeded` | 超过上下文窗口 | 缩小Condenser窗口→再压缩→兜底裁剪 | `sdk/agent/agent.py` step() |

#### 模块5：工具层 — `tools/` (~430行)

| 类/函数 | 核心职责 | 关键方法 | 数据流向 |
|---------|---------|---------|---------|
| `ToolDefinition[A,O]` | 工具定义泛型基类 | `name` / `description` / `schema` / `execute()` | 注册→发现→执行 |
| `DeclaredResources` | 声明式并发控制 | `resources: dict[str, Lock]` + `acquire()` / `release()` | 并行执行时资源互斥 |
| `ToolRegistry` | 工具注册表 | `register()` / `get()` / `list_tools()` | 注册→发现 |
| `ParallelToolExecutor` | 并行工具执行 | `execute_parallel(actions)` → `asyncio.gather` | 多Action并行执行 |
| `TerminalTool` | Bash命令执行 | `execute(BashAction)` → `subprocess.run()` | Action→subprocess→Observation |
| `FileEditorTool` | 文件编辑 | `execute(FileEditAction)` → view/str_replace/create | Action→文件IO→Observation |
| `FinishTool` | 任务结束 | `execute(FinishAction)` → 返回结束信号 | Action→终止信号 |

**ToolDefinition 泛型设计：**
```
ToolDefinition[ActionT, ObservationT]
  ├── ActionT: 继承自Action，定义输入Schema
  ├── ObservationT: 继承自Observation，定义输出Schema
  ├── execute(action: ActionT) → ObservationT
  └── to_schema() → JSON Schema（注入security_risk字段）
```

**DeclaredResources 并发控制流程：**
```
ParallelToolExecutor.execute_parallel([action1, action2])
  1. 收集每个工具的 declared_resources
  2. 检测资源冲突（同一资源键）
  3. 有冲突 → 串行执行（先获取锁）
  4. 无冲突 → asyncio.gather 并行执行
  5. 释放所有资源锁
```

**工具注册发现机制：**
```python
# 注册（启动时）
registry.register("bash", TerminalTool)
registry.register("file_edit", FileEditorTool)
registry.register("finish", FinishTool)

# 发现（Agent step时）
tools_schema = [registry.get(name).to_schema() for name in registry.list_tools()]
# → 注入到LLM的function_calling参数
```

#### 模块6：安全层 — `security/` (~120行)

| 类/函数 | 核心职责 | 关键方法 | 数据流向 |
|---------|---------|---------|---------|
| `SecurityAnalyzerBase`(ABC) | 安全分析抽象 | `analyze(action)` → `SecurityRisk` | Agent→Analyzer→风险评估 |
| `PatternSecurityAnalyzer` | 正则模式匹配 | `analyze()` → 匹配危险命令模式 | Action→正则匹配→风险等级 |
| `ConfirmationPolicy` | 确认策略枚举 | `NEVER` / `RISKY` / `ALWAYS` | 风险等级→是否需确认 |
| `inject_security_risk()` | Schema安全增强 | 修改工具JSON Schema注入`security_risk`字段 | 工具Schema→LLM感知风险 |

**安全检查流程：**
```
Agent收到Action
  → PatternSecurityAnalyzer.analyze(action)
  → 匹配危险模式（rm -rf /, sudo, curl|sh等）
  → 返回 risk_level: LOW / MEDIUM / HIGH
  → ConfirmationPolicy 判断:
      NEVER   → 直接执行
      RISKY   → HIGH风险需用户确认
      ALWAYS  → 所有Action需用户确认
```

**security_risk Schema注入：**
```json
{
  "name": "bash",
  "parameters": {
    "properties": {
      "command": {"type": "string"},
      "security_risk": {"type": "string", "description": "HIGH: 可能修改/删除文件"}
    }
  }
}
```
→ LLM在决策时能"看到"每个工具调用的风险等级，倾向于选择更安全的方案

#### 模块7：Prompt层 — `prompt/` (~110行)

| 类/函数 | 核心职责 | 关键方法 | 数据流向 |
|---------|---------|---------|---------|
| `SystemPromptBuilder` | 动态Prompt组装 | `build()` → System + Tools + Skills + Context | Agent→Builder→完整prompt |
| `SkillLoader` | Skill文件加载 | `load_from_dir()` → 解析Markdown元数据 | 本地目录→Skill列表 |
| `KeywordTrigger` | 关键词匹配触发 | `match(message)` → 匹配的Skill | 用户消息→Skill→注入上下文 |

**Prompt组装顺序（与OpenHands一致）：**
```
1. System基础指令（Jinja2模板渲染）
2. 工具Schema列表（从Registry动态获取）
3. 匹配的Skill内容（KeywordTrigger匹配）
4. 对话历史（Condenser压缩后）
5. 用户当前消息
```

#### 模块8：LLM层 — `llm/llm.py` (~80行)

| 类/函数 | 核心职责 | 关键方法 | 数据流向 |
|---------|---------|---------|---------|
| `LLM` | litellm统一封装 | `completion(messages, tools)` → 响应 | Agent→litellm→LLM响应 |
| `extract_action()` | 响应解析 | 从tool_calls提取Action | LLM响应→Action对象 |
| `extract_message()` | 消息提取 | 从content提取文本响应 | LLM响应→消息字符串 |

**LLM配置（复用本地运行指南的京东云配置）：**
```python
# 支持任何litellm兼容模型
llm = LLM(model="openai/your-model", api_key="...", base_url="...")
```

#### 模块9：CLI入口 — `main.py` (~80行)

| 函数 | 核心职责 | 关键逻辑 | 数据流向 |
|------|---------|---------|---------|
| `main()` | 程序入口 | 初始化所有组件 → 进入交互循环 | 启动→Agent |
| `interactive_loop()` | 用户交互循环 | 读取输入→Agent.step()→输出结果→循环 | 用户↔Agent |
| `handle_user_confirm()` | 安全确认处理 | 展示风险→等待y/n→返回决策 | Security→用户→Agent |

**CLI交互流程：**
```
$ python -m mini_openhands
> 帮我创建一个hello.py文件
  [Agent] 调用 FileEditTool(create, hello.py, "print('hello')")
  [Observation] 文件 hello.py 已创建
> 运行 hello.py
  [Agent] 调用 TerminalTool(python hello.py)
  [Observation] hello
> 任务完成
  [Agent] 调用 FinishTool("任务已完成")
```

### 6.5 mini-openhands 与 OpenHands 架构映射

| mini-openhands 模块 | OpenHands 对应源码 | 架构差异 |
|--------------------|--------------------|---------|
| `core/schema.py` | `sdk/utils/models.py` + `sdk/tool/tool.py` | OpenHands用元类实现DiscriminatedUnion，mini版用Pydantic model_validator |
| `core/event.py` | `sdk/event/` + `server/event_service/` | OpenHands有S3/GCS持久化后端，mini版仅内存列表 |
| `core/condenser.py` | `sdk/context/condenser/` | OpenHands有6种策略+独立LLM，mini版3种策略+共享LLM |
| `agent/agent.py` | `sdk/agent/agent.py` | OpenHands有8阶段+Critic+Hook，mini版5阶段简化 |
| `tools/tool_definition.py` | `sdk/tool/tool.py` | 核心设计一致，OpenHands额外有MCP动态适配 |
| `tools/parallel_executor.py` | `sdk/tool/parallel_tool_executor.py` | 核心并发逻辑一致，OpenHands有更完善的ResourceLockManager |
| `security/analyzer.py` | `sdk/security/` | OpenHands有5层纵深防御，mini版仅Pattern+Policy |
| `prompt/` | `openhands/prompts/` + `sdk/skill/` | OpenHands有5源Skill+Hook+Plugin，mini版仅本地文件加载 |
| `events/callback.py` | `server/event_callback/` | OpenHands有Webhook+JWT，mini版仅SetTitle |
| `llm/llm.py` | `sdk/llm/` | OpenHands有Completion+Responses双API+Router，mini版仅Completion |

---

## 七、结论

**mini-openhands 能帮你掌握 OpenHands 约 70% 的核心设计思想，但只有约 5% 的工程实现细节。**

这恰恰是最优的学习策略：
- **70% 的设计思想** = 最有价值的部分（架构模式、异常恢复、声明式并发、策略模式、事件解耦）
- **95% 的工程细节** = 生产必需但学习价值较低的部分（Docker沙箱、JWT认证、PostgreSQL持久化、WebSocket推送、多Git Provider适配）

**建议：** 先造 mini-openhands 掌握设计思想，再对照源码补 Critic/Hook/MCP 三个关键盲区，最后从全局视角理解 DI 体系和对话全链路。2周内可完全掌握 OpenHands 的设计精髓。
