#!/usr/bin/env python3
"""Fix architecture analysis report based on source code verification results."""

import re

REPORT_PATH = "/Users/gechunfa1/Documents/ai-code/tool_use_coll/openhands_architecture_analysis.md"

with open(REPORT_PATH, "r", encoding="utf-8") as f:
    content = f.read()

# Fix 1: Agent class description
content = content.replace(
    "**核心类**：`Agent(AgentBase)` 位于 `openhands.sdk.agent.agent`",
    "**核心类**：`Agent(CriticMixin, ResponseDispatchMixin, AgentBase)` 位于 `openhands.sdk.agent.agent`"
)

# Fix 2: Agent step() flow
old_step = """```
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
```"""

new_step = """```
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
```"""

content = content.replace(old_step, new_step)

# Fix 3: Conversation state machine
old_sm = """**ConversationState**：管理对话执行状态（7种状态）：
- IDLE → RUNNING → FINISHED/ERROR/STUCK
- RUNNING → PAUSED → WAITING_FOR_CONFIRMATION
- 包含 EventStore、SecretRegistry、ResourceLockManager"""

new_sm = """**ConversationState**：管理对话执行状态（8种状态）：
- IDLE / PAUSED / ERROR / STUCK → RUNNING（run() 启动时自动转换）
- RUNNING → FINISHED（Agent完成或Hook允许停止）
- RUNNING → WAITING_FOR_CONFIRMATION（安全策略要求确认时break）
- FINISHED 时 Hook 可拒绝停止，回退到 RUNNING 继续
- WAITING_FOR_CONFIRMATION → RUNNING（下次run()确认后）
- DELETING（对话删除中）
- 终态：FINISHED / ERROR / STUCK（is_terminal()判断，IDLE不是终态）
- 包含 EventStore、SecretRegistry、ResourceLockManager"""

content = content.replace(old_sm, new_sm)

# Fix 4: LLM dual mode detail
old_llm = """功能特性：
- 基于 **litellm** 统一 100+ LLM 提供商接口
- 支持 **Completion API** 和 **Responses API** 双模式
- 流式输出（Streaming）+ Token 计数
- 自动重试（RetryMixin）+ 降级策略（FallbackStrategy）
- 多模态支持（Vision/Image）
- **LLMRegistry**：多 LLM 配置注册（主模型+Condenser模型+子代理模型）
- **LLMProfileStore**：LLM 配置档案管理
- 认证：API Key / OAuth / OpenAI Subscription Auth"""

new_llm = """功能特性：
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
- 认证：API Key / OAuth / OpenAI Subscription Auth"""

content = content.replace(old_llm, new_llm)

# Fix 5: App Server DI detail
old_di = """**依赖注入**：使用 Injector 模式，所有服务通过 FastAPI Depends 注入"""

new_di = """**依赖注入**：`AppServerConfig` 集中管理 12 个服务注入器（Injector）：
- LLMModelService / EventService / EventCallbackService / SandboxService
- AppConversationService / AppConversationInfoService / PendingMessageService
- UserContext / JwtService / HttpxClient / DbSession / WebClientConfig
- 每个 Injector 通过 FastAPI Depends 注入，支持运行时替换（Enterprise 覆盖 Injector 实现）
- `config_from_env()` 根据环境变量自动选择实现（如 RUNTIME=remote -> RemoteSandboxService）
- 全局单例 `get_global_config()` + `InjectorState` 管理注入状态"""

content = content.replace(old_di, new_di)

# Fix 6: Enterprise extension mechanism
old_ent = """**扩展方式**：
1. **堆叠**：Enterprise 中间件叠加在 OSS 中间件之上
2. **覆盖**：通过动态导入覆盖 OSS 实现（如 SaasServerConfig 覆盖 ServerConfig）"""

new_ent = """**扩展方式**：
1. **Namespace Package 堆叠**：Enterprise 模块与 OSS 模块共享 `openhands` 命名空间，可叠加中间件
2. **get_impl() 动态覆盖**：`import_utils.get_impl()` 根据 `OPENHANDS_CONFIG_CLS` 环境变量动态导入实现类（如 `server.config.SaaSServerConfig`），使用 `importlib.import_module` 加载并验证子类关系
3. **字符串类引用**：ServerConfig 中 `settings_store_class`、`secret_store_class`、`user_auth_class` 等字段通过 `import_from()` 延迟加载，Enterprise 可覆盖这些字段指向自己的实现"""

content = content.replace(old_ent, new_ent)

# Fix 7: Add verification section
verification = """
---

## 8. 验证说明

本报告所有核心描述均经过源码逐行验证：

| 验证项 | 验证方法 | 结果 |
|--------|----------|------|
| Namespace Package | 读取 openhands/__init__.py，确认 pkgutil.extend_path | 已确认 |
| Agent 继承结构 | 读取 agent.py 类定义 | CriticMixin + ResponseDispatchMixin + AgentBase |
| Agent.step() 流程 | 逐行阅读 step() 方法（475-603行） | 含 pending_actions/hook/condensation/异常处理 |
| Conversation 状态机 | 逐行阅读 LocalConversation.run()（745-888行） | 8种状态，Hook可拒绝FINISHED |
| LLM 双模式 | 逐行阅读 completion()和responses() | Completion API + Responses API |
| App Server DI | 逐行阅读 AppServerConfig + config_from_env | 12个Injector，环境变量自动选择 |
| Enterprise 扩展 | 逐行阅读 get_impl/import_from + ServerConfig | importlib动态导入+字符串类引用 |
| 源码行数 | find + wc -l 重新统计 | 与报告中数据一致 |
"""

content = content + verification

with open(REPORT_PATH, "w", encoding="utf-8") as f:
    f.write(content)

print("Report updated successfully!")
print(f"Total lines: {len(content.splitlines())}")
