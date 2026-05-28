# OpenHands 工具设计深度分析

## 1. 架构概览

OpenHands 的工具系统采用**双层包架构**，将核心抽象与具体实现分离：

| 包名 | 职责 | 关键模块 |
|------|------|----------|
| `openhands-sdk` | 工具核心抽象、注册机制、Action/Observation 基类 | `openhands.sdk.tool` |
| `openhands-tools` | 具体工具实现（终端、文件编辑、浏览器等） | `openhands.tools.*` |

工具系统的核心设计遵循 **Action-Observation** 模式，即每个工具接受一个 Action（输入动作），执行后返回一个 Observation（输出观测）。

---

## 2. 核心类层次结构

### 2.1 Schema 体系（数据模型基类）

- **DiscriminatedUnionMixin**：所有 Schema 子类都混入此特性，通过 `kind` 字段（自动设为类名）实现多态序列化/反序列化，支持 JSON 数据自动路由到正确的子类。
- **frozen=True**：Schema 实例不可变，保证数据完整性。
- **extra="forbid"**：禁止额外字段，严格校验。
- **to_mcp_schema() / from_mcp_schema()**：支持与 MCP JSON Schema 的双向转换。

Action 子类包括: TerminalAction, FileEditorAction, GlobAction, GrepAction, TaskTrackerAction, TaskAction, BrowserAction(及其14个子类), MCPToolAction, FinishAction, ThinkAction, InvokeSkillAction 等。

Observation 子类包括: TerminalObservation, FileEditorObservation, GlobObservation, GrepObservation, TaskTrackerObservation, BrowserObservation, MCPToolObservation, FinishObservation, ThinkObservation 等。

### 2.2 ToolDefinition 体系（工具定义基类）

ToolDefinition[ActionT, ObservationT] 是所有工具的核心基类，子类包括：
- FinishTool / ThinkTool / InvokeSkillTool (内置)
- TerminalTool / FileEditorTool / GlobTool / GrepTool
- TaskTrackerTool / TaskTool / TaskToolSet
- BrowserToolSet (聚合14个浏览器子工具)
- MCPToolDefinition (MCP动态工具)
- EditTool / ReadFileTool / WriteFileTool / ListDirectoryTool (Gemini风格)
- PlanningFileEditorTool / TomConsultTool / SleeptimeComputeTool

---

## 3. 工具定义详解：ToolDefinition

`ToolDefinition` 是所有工具的核心基类，定义在 `openhands.sdk.tool.tool` 中。

### 3.1 核心字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `name` | ClassVar[str] | 工具名称，自动从类名生成（CamelCase -> snake_case） |
| `description` | str | 工具描述，LLM 通过此理解工具用途 |
| `action_type` | type[Action] | 输入动作的 Pydantic 模型类 |
| `observation_type` | type[Observation] \| None | 输出观测的 Pydantic 模型类 |
| `executor` | ToolExecutor \| None | 运行时执行器（序列化时排除） |
| `annotations` | ToolAnnotations \| None | 工具行为标注 |
| `meta` | dict \| None | 自定义元数据 |

### 3.2 自动命名机制

```python
def __init_subclass__(cls, **kwargs):
    super().__init_subclass__(**kwargs)
    if "name" not in cls.__dict__:
        cls.name = _camel_to_snake(cls.__name__).removesuffix("_tool")
```

示例：TerminalTool -> terminal, FileEditorTool -> file_editor, BrowserToolSet -> browser_tool_set

### 3.3 抽象工厂方法 create()

每个工具子类必须实现 `create()` 方法，负责：
1. 从 `ConversationState` 获取运行时参数（如工作目录）
2. 初始化 `ToolExecutor`
3. 构建增强的工具描述（注入工作目录等信息）
4. 返回工具实例列表（支持一个 create 产出多个工具，如 BrowserToolSet）

### 3.4 执行调用 __call__()

执行流程：检查 executor -> 调用 executor(action, conversation) -> 强制转换结果为 observation_type

### 3.5 LLM 工具格式转换

- `to_openai_tool()` -> OpenAI Function Calling 格式
- `to_responses_tool()` -> Responses API 格式
- `to_mcp_tool()` -> MCP 工具定义格式

### 3.6 安全增强

在导出给 LLM 的 Schema 中动态注入：
- `security_risk` 字段（仅非只读工具）：LLM 预测动作的安全风险等级
- `summary` 字段（始终添加）：约10词描述动作目的，提升可解释性

---

## 4. ToolExecutor（工具执行器）

```python
class ToolExecutor[ActionT, ObservationT](ABC):
    @abstractmethod
    def __call__(self, action, conversation=None):
        # 执行工具并返回观测结果
        pass
    def close(self) -> None:
        # 清理资源（可选覆写）
        pass
```

设计特点：泛型参数化保证类型安全；接收 conversation 参数可访问对话上下文；执行器与定义分离

---

## 5. ToolAnnotations（工具行为标注）

基于 MCP 规范的工具行为标注：

| 标注 | 默认值 | 说明 |
|------|--------|------|
| `title` | None | 人类可读的工具标题 |
| `readOnlyHint` | False | 是否为只读操作 |
| `destructiveHint` | True | 是否可能执行破坏性操作 |
| `idempotentHint` | False | 相同参数重复调用是否幂等 |
| `openWorldHint` | True | 是否与外部世界交互 |

---

## 6. DeclaredResources（并行执行资源声明）

```python
@dataclass(frozen=True, slots=True)
class DeclaredResources:
    keys: tuple[str, ...]   # 资源标识符，如 "file:/path/to/file"
    declared: bool          # 是否已声明
```

三种状态：
- declared=False（默认）：保守序列化（工具级互斥锁）
- declared=True, keys=()：完全并行
- declared=True, keys=(...)：按资源键加锁

---

## 7. 工具注册机制

Registry 架构：`_REG: dict[str, Resolver]` 全局注册表

注册方式：`register_tool(name, factory)` 支持三种 factory：
1. ToolDefinition 实例（必须已有 executor）
2. ToolDefinition 子类（必须有 create() 方法）
3. 可调用工厂函数

自动注册：每个工具模块在导入时自动注册
工具解析：`resolve_tool(tool_spec, conv_state)` 根据规格产出实际实例

---

## 8. 工具规格：Tool

```python
class Tool(BaseModel):
    name: str        # 工具类名
    params: dict     # create() 参数
```

---

## 9. MCP 工具集成

MCPToolDefinition 动态适配 MCP 工具到 OpenHands 体系：
- 动态从 inputSchema 创建 Action 类型
- MCPToolExecutor 通过 MCPClient 异步调用工具
- Schema.from_mcp_schema() 将 MCP JSON Schema 转换为 Pydantic 模型

---

## 10. 工具分类总览

| 类别 | 工具 | 动作数 | 说明 |
|------|------|--------|------|
| 终端 | TerminalTool | 1 | Shell命令执行 |
| 文件编辑 | FileEditorTool | 5种命令 | view/create/str_replace/insert/undo_edit |
| 文件搜索 | GlobTool | 1 | Glob模式文件匹配 |
| 内容搜索 | GrepTool | 1 | 正则内容搜索 |
| 任务追踪 | TaskTrackerTool | 2种命令 | view/plan |
| 子代理 | TaskToolSet | 1 | 启动子代理任务 |
| 浏览器 | BrowserToolSet | 14 | 导航/点击/输入/截图等 |
| MCP | MCPToolDefinition | 动态 | 外部MCP服务器工具 |
| Gemini风格 | Edit/ReadFile/WriteFile/ListDirectory | 4 | Gemini模型优化 |
| 规划 | PlanningFileEditorTool | 5 | 仅可编辑PLAN.md |
| Tom咨询 | TomConsult/SleeptimeCompute | 2 | 用户建模 |
| 内置 | Finish/Think/InvokeSkill | 3 | Agent必需 |

---

## 11. 工具调用完整流程

1. Agent 初始化：解析 Tool 规格 -> resolve_tool -> ToolClass.create() -> 初始化 executor
2. LLM 推理：选择工具 -> 生成参数 -> 返回 tool_call
3. 工具执行：查找 ToolDefinition -> 构建 Action -> 执行 -> 返回 Observation
4. 结果处理：to_llm_content -> 发送回 LLM

---

## 12. 设计模式总结

| 模式 | 应用 | 说明 |
|------|------|------|
| Strategy | ToolExecutor | 执行逻辑与定义解耦 |
| Template Method | ToolDefinition.__call__() | 固定执行流程 |
| Factory Method | ToolDefinition.create() | 自定义实例化逻辑 |
| Registry | register_tool/resolve_tool | 全局注册表 |
| Discriminated Union | DiscriminatedUnionMixin | 多态序列化 |
| Protocol | ExecutableTool | 类型安全协议 |
| Resource Declaration | DeclaredResources | 声明式并发控制 |
| Adapter | MCPToolDefinition | MCP工具适配 |

关键设计决策：定义与执行分离；Action-Observation统一协议；声明式配置；自动注册；动态Schema生成；安全增强；并行安全声明；工具集模式；多格式适配；不可变数据模型
