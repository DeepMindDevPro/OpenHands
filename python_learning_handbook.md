# Python 学习手册：从 Java 到 AI Agent 开发

> 面向 Java 工程师的 Python 系统学习指南
> 基于 OpenHands 项目真实代码，循序渐进，5 阶段进阶

---

# 学习路线图

```
阶段1 基础语法          阶段2 数据建模          阶段3 Web开发
  变量/函数/类    →     Pydantic/Enum     →    FastAPI/SQLAlchemy
                                                            ↓
                                              阶段5 项目实战          阶段4 异步编程
                                               OpenHands架构    ←    asyncio/httpx
```

- **阶段1-2**（1-2周）：每天 1-2 小时，手写练习
- **阶段3-4**（2-3周）：结合项目代码阅读
- **阶段5**（持续）：在项目中实践

---

# 阶段 1：Python 基础 — 你已经会 70%

> Java 工程师学 Python，最大的障碍不是语法，而是思维习惯。
> Python 的哲学是"简单胜于复杂"，能用一行解决的绝不用五行。

---

## 1.1 变量与类型 — 不需要写类型，但可以写

**Java 中**：
```java
String name = "OpenHands";
int count = 42;
boolean isActive = true;
List<String> items = new ArrayList<>();
```

**Python 中**：
```python
name = "OpenHands"          # 不用声明类型
count = 42
is_active = True            # 注意大写 T
items = []                  # 空列表
```

**但你可以在 Python 中加类型注解**（项目中的真实写法）：
```python
# 来自 openhands/app_server/config.py
def get_default_web_url() -> str | None:
    web_host = os.getenv('WEB_HOST')
    if not web_host:
        return None
    return f'https://{web_host}'
```

**关键区别**：
| 概念 | Java | Python |
|------|------|--------|
| 声明变量 | `String s = "hi"` | `s = "hi"` 或 `s: str = "hi"` |
| 可空类型 | `Optional<String>` | `str \| None` |
| 命名规范 | camelCase | snake_case |
| 语句结束 | 分号 `;` | 换行 |
| 代码块 | 大括号 `{ }` | 缩进（4空格） |
| 常量 | `final` | 全大写约定 `MAX_SIZE` |

---

## 1.2 数据结构大全 — 这是 Python 最强的部分

> Python 的内置数据结构比 Java 丰富得多，
> Java 需要 `ArrayList`、`HashMap`、`HashSet` 各种工具类，
> Python 用 `[]`、`{}`、`set()` 就搞定了。

---

### 1.2.1 list — 对应 Java 的 ArrayList

```python
# 创建
nums = [1, 2, 3]                          # Java: List<Integer> nums = new ArrayList<>(List.of(1,2,3));
empty = []                                 # Java: new ArrayList<>()
from_range = list(range(5))                # [0, 1, 2, 3, 4]

# 读取
nums[0]                                    # 1（和 Java 一样从 0 开始）
nums[-1]                                   # 3（倒数第一个！Java 没有这个）
nums[1:3]                                  # [2, 3]（切片，Java 需要 subList）

# 修改
nums.append(4)                             # Java: nums.add(4)
nums.extend([5, 6])                        # Java: nums.addAll(List.of(5, 6))
nums.insert(0, 0)                          # Java: nums.add(0, 0)
nums.pop()                                 # Java: nums.remove(nums.size()-1) — 删除并返回末尾
nums.pop(0)                                # 删除并返回第一个
nums.remove(2)                             # Java: nums.remove(Integer.valueOf(2)) — 按值删除

# 查找
3 in nums                                  # Java: nums.contains(3) — 返回 True/False
nums.index(3)                              # Java: nums.indexOf(3)
nums.count(3)                              # Java: Collections.frequency(nums, 3)
len(nums)                                  # Java: nums.size()

# 排序
nums.sort()                                # Java: nums.sort(null) — 原地排序
sorted(nums)                               # Java: nums.stream().sorted().toList() — 返回新列表
nums.sort(reverse=True)                    # 降序
nums.sort(key=lambda x: x.name)            # Java: nums.sort(Comparator.comparing(X::getName))

# 列表推导（最常用！替代 Java Stream）
doubled = [n * 2 for n in nums]            # Java: nums.stream().map(n -> n*2).toList()
evens = [n for n in nums if n % 2 == 0]    # Java: nums.stream().filter(n -> n%2==0).toList()

# 项目实例来自 openhands/app_server/app_conversation/app_conversation_router.py
uuids: list[UUID] = []
invalid_ids: list[str] = []
for id_str in ids:
    try:
        uuids.append(UUID(id_str))         # append 是最常用的操作
    except ValueError:
        invalid_ids.append(id_str)
```

**切片详解**（Java 没有的强大特性）：
```python
a = [0, 1, 2, 3, 4, 5]
a[2:5]      # [2, 3, 4]     — 从索引 2 到 4（不含 5）
a[:3]       # [0, 1, 2]     — 前 3 个
a[3:]       # [3, 4, 5]     — 从第 3 个到末尾
a[-2:]      # [4, 5]        — 最后 2 个
a[::2]      # [0, 2, 4]     — 每隔 1 个取
a[::-1]     # [5, 4, 3, 2, 1, 0]  — 反转
```

---

### 1.2.2 tuple — 不可变的 list（对应 Java 的 record 字段）

```python
# 创建
point = (3, 4)                             # 不可变！创建后不能修改
single = (42,)                             # 注意：单元素 tuple 必须加逗号
empty = ()

# 读取（和 list 一样）
point[0]                                   # 3
point[-1]                                  # 4

# 解包（Java 没有的！）
x, y = point                               # x=3, y=4 — 一行完成多变量赋值

# 项目实例来自 openhands/app_server/integrations/service_types.py
# 函数返回多个值
response, headers = await self._make_request(url, params)
# Java 对比：需要定义 Pair<Response, Headers> 或 Record

# tuple 作为字典的 key（list 不行！）
cache = {}
cache[(user_id, repo_name)] = data         # 用 tuple 做复合 key

# 项目实例来自 openhands/app_server/constants.py
BLOCKED_SECRET_PREFIXES: tuple[str, ...] = ('LLM_',)
# tuple[str, ...] 表示元素数量不固定的字符串元组
```

**list vs tuple 怎么选？**

| 场景 | 用 list | 用 tuple |
|------|---------|----------|
| 需要增删元素 | ✅ | ❌ |
| 作为字典 key | ❌ | ✅ |
| 函数返回多值 | 可以 | ✅ 更语义化 |
| 不可变常量 | ❌ | ✅ |

---

### 1.2.3 dict — 对应 Java 的 HashMap

```python
# 创建
config = {'host': 'localhost', 'port': 5432}    # Java: new HashMap<>()
empty = {}                                       # Java: new HashMap<>()
from_pairs = dict(a=1, b=2)                      # {'a': 1, 'b': 2}

# 读取
config['host']                                   # 'localhost' — 不存在会 KeyError！
config.get('host')                               # 'localhost' — 不存在返回 None
config.get('missing', 'default')                 # 'default' — 不存在返回默认值

# 修改
config['user'] = 'admin'                         # Java: config.put("user", "admin")
config.update({'port': 3306, 'db': 'test'})      # Java: config.putAll(...)
del config['user']                               # Java: config.remove("user")
config.pop('port')                               # 删除并返回值

# 遍历
for key in config:                               # 遍历 key
    print(key)
for key, value in config.items():                # Java: config.forEach((k, v) -> ...)
    print(f'{key}={value}')
for value in config.values():                    # 遍历 value
    print(value)

# 查找
'host' in config                                 # Java: config.containsKey("host")
len(config)                                      # Java: config.size()

# 设置默认值（Java 没有的便捷方法）
config.setdefault('timeout', 30)                 # 如果 key 不存在才设置

# 字典推导
squares = {n: n**2 for n in range(5)}            # {0:0, 1:1, 2:4, 3:9, 4:16}

# 合并字典（Python 3.9+）
merged = config | {'new_key': 'new_value'}       # Java: Stream.concat + Collectors.toMap

# 项目实例来自 openhands/app_server/settings/llm_profiles.py
profiles: dict[str, LLM] = Field(default_factory=dict)
# 遍历并构建新字典
renamed: dict[str, LLM] = {
    (new_name if key == old_name else key): llm
    for key, llm in self.profiles.items()        # 字典推导 + 条件
}

# 项目实例来自 openhands/app_server/utils/jsonpatch_compat.py — 深度合并
def deep_merge(base: dict[str, Any], updates: dict[str, Any]) -> dict[str, Any]:
    result = dict(base)                          # 浅拷贝
    for key, value in updates.items():
        if value is None:
            result.pop(key, None)                # None 值表示删除
        elif isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = deep_merge(result[key], value)  # 递归合并
        else:
            result[key] = value                  # 直接覆盖
    return result
```

---

### 1.2.4 set — 对应 Java 的 HashSet

```python
# 创建
fruits = {'apple', 'banana', 'orange'}           # Java: new HashSet<>(List.of(...))
empty = set()                                     # 注意：{} 是空字典，不是空 set！
from_list = set([1, 2, 2, 3])                     # {1, 2, 3} — 自动去重

# 修改
fruits.add('grape')                               # Java: fruits.add("grape")
fruits.remove('apple')                            # Java: fruits.remove("apple") — 不存在会 KeyError
fruits.discard('apple')                           # 不存在也不报错（更安全）
fruits.update(['kiwi', 'mango'])                  # Java: fruits.addAll(...)

# 集合运算（Java 需要手动操作）
a = {1, 2, 3}
b = {2, 3, 4}
a | b                                             # {1,2,3,4} — 并集
a & b                                             # {2,3} — 交集
a - b                                             # {1} — 差集
a ^ b                                             # {1,4} — 对称差集

# 查找
'apple' in fruits                                 # Java: fruits.contains("apple")
len(fruits)                                       # Java: fruits.size()

# 项目实例来自 openhands/app_server/constants.py
BLOCKED_SECRET_NAMES: frozenset[str] = frozenset({
    'OPENVSCODE_SERVER_ROOT',
    'OH_ENABLE_VNC',
    'LOG_JSON',
    # ...
})
# frozenset — 不可变的 set，可以作为字典 key
```

**set vs frozenset**：
| 场景 | 用 set | 用 frozenset |
|------|--------|-------------|
| 需要增删 | ✅ | ❌ |
| 作为字典 key | ❌ | ✅ |
| 不可变常量 | ❌ | ✅ |

---

### 1.2.5 str — 字符串（比 Java String 强大得多）

```python
s = "Hello, World!"

# 基本操作（和 Java 类似）
len(s)                                            # 13
s[0]                                              # 'H'
s[-1]                                             # '!'
s[7:12]                                           # 'World' — 切片！Java 需要 substring

# 查找
s.startswith('Hello')                             # Java: s.startsWith("Hello")
s.endswith('!')                                   # Java: s.endsWith("!")
'World' in s                                      # Java: s.contains("World")
s.find('World')                                   # Java: s.indexOf("World")
s.count('l')                                      # Java 没有直接等价

# 变换
s.lower()                                         # Java: s.toLowerCase()
s.upper()                                         # Java: s.toUpperCase()
s.strip()                                         # Java: s.trim()
s.replace('World', 'Python')                      # Java: s.replace("World", "Python")
s.split(',')                                      # Java: s.split(",") — 返回 list
','.join(['a', 'b', 'c'])                         # Java: String.join(",", list) — 注意调用顺序！

# 判断
s.isalpha()                                       # 是否全是字母
s.isdigit()                                       # 是否全是数字
s.isempty = len(s) == 0                           # Python 没有 isEmpty()，用 len 或 not

# 项目实例来自 openhands/app_server/event_callback/webhook_router.py
msg_lower = error_message.lower()
if 'budget' in msg_lower or 'budgetexceeded' in msg_lower:
    return 'budget_exceeded'
if any(kw in msg_lower for kw in ('model', 'llm', 'api key', 'rate limit')):
    return 'model_error'
```

---

### 1.2.6 collections — 高级数据结构（Java 的 Guava 等价物）

#### defaultdict — 自动初始化的字典

```python
# Java 中你需要:
# Map<String, List<String>> groups = new HashMap<>();
# groups.computeIfAbsent("key", k -> new ArrayList<>()).add("value");

# Python 中:
from collections import defaultdict

groups = defaultdict(list)                        # 不存在的 key 自动创建空列表
groups['fruits'].append('apple')                  # 不用先初始化！
groups['fruits'].append('banana')
# groups = {'fruits': ['apple', 'banana']}

counter = defaultdict(int)                        # 不存在的 key 自动为 0
counter['a'] += 1                                 # 不用先初始化！
counter['a'] += 1
# counter = {'a': 2}

# 项目实例来自 openhands/app_server/middleware.py
class InMemoryRateLimiter:
    def __init__(self):
        self.history = defaultdict(list)           # 每个 IP 的请求历史
        # 不需要 if ip not in history: history[ip] = []
```

#### Counter — 计数器

```python
from collections import Counter

# 统计元素出现次数
words = ['apple', 'banana', 'apple', 'cherry', 'apple']
counts = Counter(words)                           # {'apple': 3, 'banana': 1, 'cherry': 1}

counts.most_common(2)                             # [('apple', 3), ('banana', 1)] — 前 N 个
counts['orange']                                  # 0（不存在的返回 0，不报错）
```

#### deque — 双端队列

```python
from collections import deque

# Java: ArrayDeque<String>
queue = deque(['a', 'b', 'c'])
queue.appendleft('x')                             # 左端添加 O(1)
queue.pop()                                       # 右端删除 O(1)
queue.popleft()                                   # 左端删除 O(1)

# 比 list 的 insert(0, x) 快得多（list 是 O(n)）
```

---

### 1.2.7 数据结构选择指南

| 需求 | Python | Java 等价 | 特点 |
|------|--------|-----------|------|
| 有序可变集合 | `list` | `ArrayList` | 最常用 |
| 有序不可变集合 | `tuple` | `Record` 字段 | 可做字典 key |
| 键值映射 | `dict` | `HashMap` | 极常用 |
| 去重 | `set` | `HashSet` | 无序 |
| 去重+不可变 | `frozenset` | `Collections.unmodifiableSet` | 可做字典 key |
| 自动初始化字典 | `defaultdict` | Guava `Multimap` | 省去判空 |
| 计数 | `Counter` | Guava `Multiset` | 一行统计 |
| 双端队列 | `deque` | `ArrayDeque` | O(1) 头部操作 |
| 字符串 | `str` | `String` | 不可变，支持切片 |

---

### 1.2.8 内建函数速查 — 替代 Java Stream

```python
nums = [3, 1, 4, 1, 5, 9, 2, 6]

# 聚合
len(nums)                                         # 8 — Java: nums.size()
sum(nums)                                         # 31 — Java: nums.stream().mapToInt(i->i).sum()
min(nums)                                         # 1 — Java: nums.stream().min()
max(nums)                                         # 9 — Java: nums.stream().max()

# 查找
any(n > 5 for n in nums)                          # True — Java: nums.stream().anyMatch(n -> n > 5)
all(n > 0 for n in nums)                          # True — Java: nums.stream().allMatch(n -> n > 0)

# 排序
sorted(nums)                                      # [1,1,2,3,4,5,6,9] — 返回新列表
sorted(nums, reverse=True)                        # [9,6,5,4,3,2,1,1]
sorted(users, key=lambda u: u.name)               # Java: sorted by comparator

# 变换
list(map(str, nums))                              # ['3','1','4',...] — Java: stream().map()
list(filter(lambda n: n > 3, nums))               # [4,5,9,6] — Java: stream().filter()

# 组合
list(zip(['a','b','c'], [1,2,3]))                 # [('a',1),('b',2),('c',3)]
list(enumerate(['a','b','c']))                    # [(0,'a'),(1,'b'),(2,'c')]

# 项目实例来自 openhands/app_server/services/jwt_service.py
newest_key = max(active_keys, key=lambda k: k.created_at)
# Java: activeKeys.stream().max(Comparator.comparing(Key::getCreatedAt)).orElseThrow()
```

---

## 1.3 字符串 — f-string 是你的好朋友

```python
# Java: String.format("Hello %s, count=%d", name, count)
# Python: f-string，直接嵌入变量
conversation_id = "abc-123"
f'Conversation {conversation_id} not found'     # 最常用

# 多行字符串（Java 中要用 StringBuilder）
message = f"""
Your session has expired.
Please login again at {host_url}
"""

# 项目实例来自 enterprise/integrations/utils.py
HOST_URL = f'https://{HOST}'
GITLAB_WEBHOOK_URL = f'{HOST_URL}/integration/gitlab/events'
```

---

## 1.4 条件与循环 — 几乎一样，更简洁

```python
# if-elif-else（注意冒号和缩进，没有括号）
if sandbox.status == SandboxStatus.RUNNING:
    return await call_next(request)
elif sandbox.status == SandboxStatus.PAUSED:
    return None
else:
    raise HTTPException(status_code=404)

# for 循环（Java 的增强 for）
for exposed_url in sandbox.exposed_urls:
    if exposed_url.name == AGENT_SERVER:
        agent_server_url = exposed_url.url
        break

# 遍历带索引（Java 的 for-i）
for i, item in enumerate(items):
    print(f"第{i}项: {item}")
```

**Python 特有的简洁写法**：
```python
# 三元表达式
# Java: String result = x != null ? x : "default"
result = x or "default"                # 短路求值，更常用
result = x if x else "default"         # 三元表达式

# 项目实例来自 openhands/app_server/config.py
persistence_dir = os.getenv('OH_PERSISTENCE_DIR') or os.getenv('FILE_STORE_PATH') or None
```

---

## 1.5 函数 — 默认参数、可变参数

```python
# 基本函数
def get_project_dir(working_dir: str, selected_repository: str | None = None) -> str:
    if selected_repository:
        repo_name = selected_repository.split('/')[-1]
        return f'{working_dir}/{repo_name}'
    return working_dir

# Java 对比：
# String getProjectDir(String workingDir, @Nullable String selectedRepository)

# 关键字参数调用（Java 没有的）
result = get_project_dir(
    working_dir="/workspace",
    selected_repository="owner/repo"     # 可以按名字传参，不用记顺序
)
```

---

## 1.6 异常处理 — try/except 代替 try/catch

```python
# Java: try { ... } catch (IllegalArgumentException e) { ... }
# Python: try/except

try:
    uuids.append(UUID(id_str))
except ValueError:                          # 不用声明异常类型
    invalid_ids.append(id_str)

# 项目实例来自 openhands/analytics/analytics_context.py
try:
    user = await provider.get_user_by_id(user_id)
    if user is None:
        return AnalyticsContext(user_id=user_id, consented=False, ...)
    return AnalyticsContext(user_id=user_id, consented=True, ...)
except Exception:                           # 捕获所有异常
    logger.warning('resolve_analytics_context failed for user_id=%s', user_id)
    return AnalyticsContext(user_id=user_id, consented=False, ...)
```

**关键区别**：
| Java | Python |
|------|--------|
| `try/catch/finally` | `try/except/finally` |
| `throw new Exception()` | `raise Exception()` |
| 方法签名声明 `throws` | 不需要声明 |
| 检查异常 vs 非检查异常 | 只有非检查异常 |

---

## 1.7 导入 — 从 import 说起

```python
# Java: import com.example.UserAuth;
# Python:

import os                                    # 导入整个模块
import logging

from pathlib import Path                     # 从模块导入特定类
from uuid import UUID, uuid4                 # 导入多个

from pydantic import BaseModel, Field        # 第三方库也一样

# 项目中的典型导入来自 openhands/app_server/app_conversation/app_conversation_models.py
from datetime import datetime
from enum import Enum
from typing import Any, Literal
from uuid import UUID, uuid4
from pydantic import BaseModel, Field, SecretStr
```

---

## 1.8 模块与包 — Python 的"类路径"

```
Java:   com.openhands.app_server.config.AppServerConfig
Python: openhands.app_server.config.AppServerConfig
        ^^^^^^^^^^^^^^^^^^^^^^^^^^^ ^^^^^^^^^^^^^^^^
        包路径(目录结构)              类名
```

**Python 包 = 有 `__init__.py` 的目录**（类似 Java 的 package-info.java）

```
openhands/
├── __init__.py              ← 这让 openhands 成为包
├── app_server/
│   ├── __init__.py          ← 这让 app_server 成为子包
│   ├── config.py            ← 模块，里面有 AppServerConfig 类
│   └── middleware.py
```

---

## 1.9 练习：读懂第一段项目代码

现在试着读懂这段来自项目的代码：

```python
# 来自 openhands/app_server/config.py
def get_default_persistence_dir() -> Path:
    persistence_dir = os.getenv('OH_PERSISTENCE_DIR')
    if persistence_dir is None:
        persistence_dir = os.getenv('FILE_STORE_PATH')
    if persistence_dir:
        result = Path(persistence_dir)
    else:
        result = Path.home() / '.openhands'
    result.mkdir(parents=True, exist_ok=True)
    return result
```

**逐行对照 Java**：
```java
Path getDefaultPersistenceDir() {
    String persistenceDir = System.getenv("OH_PERSISTENCE_DIR");
    if (persistenceDir == null) {
        persistenceDir = System.getenv("FILE_STORE_PATH");
    }
    Path result;
    if (persistenceDir != null && !persistenceDir.isEmpty()) {
        result = Path.of(persistenceDir);
    } else {
        result = Path.of(System.getProperty("user.home"), ".openhands");
    }
    try { Files.createDirectories(result); } catch (IOException ignored) {}
    return result;
}
```

Python 版本行数只有 Java 的一半。这就是 Python 的力量。

---

# 阶段 2：数据建模 — Pydantic 是 Python 世界的 Lombok

> 在 Java 中，你用 `@Data` + `@Builder` + `@Valid` 定义 DTO。
> 在 Python 中，你用 **Pydantic BaseModel**，一个顶三个。

---

## 2.1 从 Java Bean 到 Pydantic Model

**Java 写法**：
```java
@Data @Builder
public class SuggestedTask {
    private ProviderType gitProvider;
    private TaskType taskType;
    private String repo;
    @Builder.Default private Integer issueNumber = 0;
    private String title;
}
```

**Python 写法**（来自项目 `openhands/app_server/integrations/service_types.py`）：
```python
class SuggestedTask(BaseModel):
    git_provider: ProviderType
    task_type: TaskType
    repo: str
    issue_number: int
    title: str
```

**就这些！你已经得到了**：
- 自动构造函数
- 自动 `toString()`
- 自动 `equals()/hashCode()`
- 自动类型校验和转换（传 `"123"` 自动转成 `123`）
- 自动 JSON 序列化/反序列化

---

## 2.2 可选字段与默认值

```python
# 来自 openhands/app_server/integrations/service_types.py
class Repository(BaseModel):
    id: str                                    # 必填
    full_name: str                             # 必填
    is_public: bool                            # 必填
    stargazers_count: int | None = None        # 可选，默认 None
    link_header: str | None = None             # 可选
    owner_type: OwnerType | None = None        # 可选
    main_branch: str | None = None             # 可选
```

**对照 Java**：
```java
// Java 等价
@Data @Builder
public class Repository {
    @NotNull private String id;
    @NotNull private String fullName;
    @NotNull private boolean isPublic;
    @Nullable private Integer stargazersCount;
    @Nullable private String linkHeader;
    @Nullable private OwnerType ownerType;
    @Nullable private String mainBranch;
}
```

**规则**：
- `str` → 必填字符串
- `str | None = None` → 可选字符串（`@Nullable`）
- `int | None = None` → 可选整数
- `= None` → 提供默认值

---

## 2.3 Field — 更精细的控制

```python
# 来自 openhands/app_server/app_conversation/app_conversation_models.py
from pydantic import Field
from uuid import uuid4

class AppConversationInfo(BaseModel):
    id: UUID = Field(default_factory=uuid4)        # 默认生成 UUID
    pr_number: list[int] = Field(default_factory=list)  # 默认空列表
    tags: dict[str, str] = Field(default_factory=dict)  # 默认空字典
    created_at: datetime = Field(default_factory=utc_now)  # 默认当前时间
```

**为什么用 `default_factory` 而不是 `default`？**

```python
# 错误写法！所有实例共享同一个列表对象
pr_number: list[int] = []          # 相当于 Java 的 static 共享

# 正确写法：每个实例创建新列表
pr_number: list[int] = Field(default_factory=list)  # 每次创建新对象
```

这和 Java 中 `@Builder.Default` 的行为一致。

---

## 2.4 SecretStr — 保护敏感数据

```python
# 来自 openhands/app_server/integrations/provider.py
from pydantic import SecretStr, Field

class ProviderToken(BaseModel):
    token: SecretStr | None = Field(default=None)    # 密码/token 字段
    user_id: str | None = Field(default=None)
    host: str | None = Field(default=None)

# 使用时
token_value = provider_token.token.get_secret_value()   # 获取真实值

# 日志中自动脱敏 — 打印 ProviderToken 时 token 显示 '**********'
# 等价于 Java 中用 char[] 存密码，toString() 不暴露内容
```

---

## 2.5 不可变模型 — frozen

```python
# 来自 openhands/app_server/integrations/provider.py
from pydantic import ConfigDict

class ProviderToken(BaseModel):
    token: SecretStr | None = Field(default=None)

    model_config = ConfigDict(
        frozen=True,                  # 等价于 Java: 不可变对象（final 字段）
        validate_assignment=True,     # 赋值时自动校验
    )

# frozen=True 后不能修改属性
token = ProviderToken(token=SecretStr("abc"))
token.token = SecretStr("xyz")       # ❌ 报错！FrozenInstanceError
```

---

## 2.6 模型校验 — model_validator

```python
# 来自 openhands/app_server/services/db_session_injector.py
from pydantic import model_validator

class DbSessionInjector(BaseModel):
    host: str | None = None
    port: int | None = None
    name: str | None = None

    @model_validator(mode='after')          # 等价于 @PostConstruct
    def fill_empty_fields(self):
        if self.host is None:
            self.host = os.getenv('DB_HOST')
        if self.port is None:
            self.port = int(os.getenv('DB_PORT', '5432'))
        return self
```

---

## 2.7 Enum — 枚举

```python
# 来自 openhands/app_server/sandbox/sandbox_models.py
from enum import Enum

class SandboxStatus(Enum):
    STARTING = 'STARTING'
    RUNNING = 'RUNNING'
    PAUSED = 'PAUSED'
    ERROR = 'ERROR'
    MISSING = 'MISSING'

# 使用
if sandbox.status == SandboxStatus.RUNNING:
    ...

# 获取枚举的值
status_text = sandbox.status.value     # 'RUNNING'
```

**str + Enum 混合**（更方便，可直接当字符串用）：
```python
# 来自 openhands/app_server/integrations/service_types.py
class TaskType(str, Enum):
    MERGE_CONFLICTS = 'MERGE_CONFLICTS'
    FAILING_CHECKS = 'FAILING_CHECKS'

task = TaskType.MERGE_CONFLICTS
print(task)                    # 'MERGE_CONFLICTS'（直接当字符串）
print(task == 'MERGE_CONFLICTS')  # True（和字符串比较也行）
```

---

## 2.8 dataclass — 轻量数据容器

当你不需要 Pydantic 的校验功能，只是想快速定义数据类：

```python
# 来自 openhands/app_server/app_conversation/app_conversation_router.py
from dataclasses import dataclass

@dataclass                          # 等价于 Java record 或 Lombok @Value
class AgentServerContext:
    conversation: AppConversationInfo
    sandbox: SandboxInfo
    sandbox_spec: SandboxSpecInfo
    agent_server_url: str
    session_api_key: str | None
```

**Pydantic BaseModel vs dataclass 怎么选？**

| 场景 | 用 BaseModel | 用 dataclass |
|------|-------------|-------------|
| API 请求/响应 | ✅ 有校验和序列化 | ❌ |
| 数据库模型 | ✅ | ❌ |
| 内部传递数据 | ✅ 可以 | ✅ 更轻量 |
| 需要类型转换 | ✅ 自动转换 | ❌ |

---

## 2.9 练习：定义一个 API 请求模型

试着把下面这个 Java DTO 转成 Pydantic Model：

```java
@Data @Builder
public class StartConversationRequest {
    @Nullable private String sandboxId;
    @Nullable private UUID conversationId;
    @Nullable private String initialMessage;
    @Nullable private String selectedRepository;
    @Nullable private String selectedBranch;
    @Builder.Default private List<Integer> prNumbers = new ArrayList<>();
    @Builder.Default private AgentType agentType = AgentType.DEFAULT;
}
```

<details>
<summary>参考答案</summary>

```python
class StartConversationRequest(BaseModel):
    sandbox_id: str | None = None
    conversation_id: UUID | None = None
    initial_message: str | None = None
    selected_repository: str | None = None
    selected_branch: str | None = None
    pr_numbers: list[int] = Field(default_factory=list)
    agent_type: AgentType = AgentType.DEFAULT
```

</details>

---

# 阶段 3：Web 开发 — FastAPI 是 Spring Boot 的 Python 版

> FastAPI 是目前 Python Web 开发最流行的框架。
> 如果你熟悉 Spring Boot，FastAPI 的概念几乎一一对应。

---

## 3.1 最简 API — 5 行代码启动服务

```python
# app.py — 等价于 Spring Boot 的 Application 主类
from fastapi import FastAPI

app = FastAPI(title='OpenHands')          # @SpringBootApplication

@app.get('/')                              # @GetMapping("/")
async def hello():
    return {"message": "Hello"}            # 自动转 JSON
```

```bash
uvicorn app:app --reload                   # java -jar app.jar
```

---

## 3.2 路由 — @RestController

```python
# 来自 openhands/app_server/app_conversation/app_conversation_router.py
from fastapi import APIRouter

router = APIRouter(
    prefix='/app-conversations',          # @RequestMapping("/app-conversations")
    tags=['Conversations'],               # Swagger 分组
)

@router.get('/search')                     # @GetMapping("/search")
async def search_conversations(
    title: str | None = None,             # @RequestParam(required=false)
    limit: int = 100,                     # @RequestParam(defaultValue="100")
) -> AppConversationPage:                 # 返回值自动序列化
    return await service.search(title=title, limit=limit)

@router.post('')                           # @PostMapping
async def start_conversation(
    request: StartRequest,                # @RequestBody
) -> StartTask:
    return await service.start(request)
```

**注册路由到 app**：
```python
# 来自 openhands/app_server/app.py
app.include_router(router)                # 等价于 @ComponentScan
```

---

## 3.3 依赖注入 — Spring @Autowired 的 Python 版

这是 FastAPI 最强大的特性之一：

```python
# 来自项目中的真实模式

# 第一步：定义注入器（类似 Spring 的 @Bean 方法）
db_session_dependency = depends_db_session()
httpx_client_dependency = depends_httpx_client()
service_dependency = depends_app_conversation_service()

# 第二步：在路由参数中使用（类似 @Autowired）
@router.post('')
async def start_conversation(
    request: Request,
    service: AppService = service_dependency,          # 自动注入
    db: AsyncSession = db_session_dependency,           # 自动注入
    client: httpx.AsyncClient = httpx_client_dependency,  # 自动注入
):
    ...
```

---

## 3.4 异常处理 — @ControllerAdvice

```python
# 来自 openhands/app_server/app.py

# 全局异常处理 — 等价于 @ControllerAdvice + @ExceptionHandler
@app.exception_handler(AuthenticationError)
async def authentication_error_handler(request: Request, exc: AuthenticationError):
    return JSONResponse(status_code=401, content=str(exc))

# 路由内抛异常 — 等价于 ResponseStatusException
from fastapi import HTTPException, status

raise HTTPException(
    status_code=status.HTTP_404_NOT_FOUND,
    detail=f'Conversation {conversation_id} not found',
)
```

---

## 3.5 中间件 — Filter/Interceptor

```python
# 来自 openhands/app_server/middleware.py
from starlette.middleware.base import BaseHTTPMiddleware

class CacheControlMiddleware(BaseHTTPMiddleware):    # 等价于 OncePerRequestFilter
    async def dispatch(self, request, call_next):    # preHandle + postHandle
        response = await call_next(request)           # doFilter
        response.headers['Cache-Control'] = 'no-cache'
        return response

# 注册 — 等价于 FilterRegistrationBean
app.add_middleware(CacheControlMiddleware)
```

---

## 3.6 请求参数验证 — Bean Validation 的 Python 版

```python
# 来自项目路由参数
from typing import Annotated
from fastapi import Query

@router.get('/search')
async def search(
    # @RequestParam @Size(min=1, max=100)
    limit: Annotated[int, Query(gt=0, le=100)] = 100,

    # @RequestParam @Nullable
    title: Annotated[str | None, Query(title='Filter by title')] = None,
):
    ...
```

---

## 3.7 练习：写一个 CRUD API

用 FastAPI 写一个简单的用户管理 API：

<details>
<summary>参考答案</summary>

```python
from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, Field
from uuid import uuid4

app = FastAPI(title='User API')

# 数据模型
class User(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    email: str

# 模拟数据库
users: dict[str, User] = {}

@app.post('/users', status_code=201)
async def create_user(user: User):
    users[user.id] = user
    return user

@app.get('/users/{user_id}')
async def get_user(user_id: str):
    if user_id not in users:
        raise HTTPException(status_code=404, detail='User not found')
    return users[user_id]

@app.get('/users')
async def list_users() -> list[User]:
    return list(users.values())
```

</details>

---

# 阶段 4：异步编程 — AI Agent 的核心能力

> AI Agent 需要同时和 LLM、文件系统、数据库交互，
> 异步编程是必须掌握的技能。
> 好消息：比 Java 的 CompletableFuture 简单得多。

---

## 4.1 async/await — 5 分钟入门

```python
# Java CompletableFuture:
# CompletableFuture<User> getUser() { return ...; }
# User user = getUser().get();

# Python async/await:
async def get_user(user_id: str) -> User:     # async 标记异步函数
    result = await db.get(user_id)              # await 等待异步操作
    return result

# 调用异步函数
user = await get_user("123")                   # 必须在 async 函数中用 await
```

**简单记忆**：
- `async def` = 这是个异步函数（返回 CompletableFuture）
- `await` = 等待结果（`.get()` 或 `.join()`）
- `await` 只能在 `async def` 里用

---

## 4.2 项目中的异步模式

```python
# 来自 openhands/app_server/app_conversation/live_status_app_conversation_service.py

# 模式1：异步调用链（和 Java 的 thenCompose 一样）
async def get_app_conversation(self, conversation_id: UUID) -> AppConversation | None:
    info = await self.info_service.get_info(conversation_id)      # 等价于 .thenApply()
    result = await self._build_conversations([info])              # 等价于 .thenCompose()
    return result[0]

# 模式2：异步迭代（Java 的 Flux）
async def start_conversation(self, request) -> AsyncGenerator[Task, None]:
    async for task in self._start(request):                       # 异步 for 循环
        await self.save(task)                                     # 每个元素都等待保存
        yield task                                                # yield = 返回一个元素（类似 Flux.emit）
```

---

## 4.3 后台任务 — fire and forget

```python
# 来自 openhands/app_server/app_conversation/app_conversation_router.py
import asyncio

# 等价于 Java: CompletableFuture.runAsync(task)
asyncio.create_task(_consume_remaining(async_iter, db_session, httpx_client))
# 不等待结果，继续执行
```

---

## 4.4 异步上下文管理 — try-with-resources

```python
# 来自 openhands/app_server/app.py
import contextlib

def combine_lifespans(*lifespans):
    @contextlib.asynccontextmanager                   # 等价于 AutoCloseable
    async def combined_lifespan(app):
        async with contextlib.AsyncExitStack() as stack:  # try-with-resources
            for lifespan in lifespans:
                await stack.enter_async_context(lifespan(app))
            yield                                     # 资源初始化完成
    return combined_lifespan

# 使用
async with resource as r:                             # 等价于 try (Resource r = new Resource())
    r.do_something()
# 退出 with 块后自动释放资源
```

---

## 4.5 同步代码调异步 — 最常见的坑

```python
# 来自 openhands/app_server/utils/async_utils.py

# 问题：你在同步函数中想调异步函数怎么办？
# 解决：用 asyncio.run() 或线程池

def call_async_from_sync(corofn, timeout=15, *args, **kwargs):
    """从同步代码调用异步函数"""
    def run():
        return asyncio.run(corofn(*args, **kwargs))    # 创建新事件循环
    future = EXECUTOR.submit(run)                       # 在线程池中运行
    futures.wait([future], timeout=timeout)
    return future.result()

# 反过来：从异步代码调同步函数
async def call_sync_from_async(fn, *args, **kwargs):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, lambda: fn(*args, **kwargs))
```

---

## 4.6 练习：并行请求两个 API

```python
# 需求：同时调用 GitHub API 和 GitLab API，等待两个结果
import asyncio
import httpx

async def fetch_github():
    async with httpx.AsyncClient() as client:
        resp = await client.get('https://api.github.com/users/octocat')
        return resp.json()

async def fetch_gitlab():
    async with httpx.AsyncClient() as client:
        resp = await client.get('https://gitlab.com/api/v4/users')
        return resp.json()

# 并行调用
async def fetch_both():
    github_result, gitlab_result = await asyncio.gather(
        fetch_github(),
        fetch_gitlab(),
    )
    return github_result, gitlab_result
```

---

# 阶段 5：项目实战 — OpenHands 架构中的 Python 模式

> 现在你已经掌握了 Python 基础，
> 让我们看看 OpenHands 项目中使用的核心设计模式。

---

## 5.1 依赖注入系统 — OpenHands 版的 Spring DI

OpenHands 自己实现了一套轻量 DI，核心就 30 行代码：

```python
# 来自 openhands/app_server/services/injector.py
from abc import ABC, abstractmethod
from typing import Generic, TypeVar, AsyncGenerator
import contextlib

T = TypeVar('T')

class Injector(Generic[T], ABC):
    """依赖注入器 — 每个子类管理一种资源的生命周期"""

    @abstractmethod
    async def inject(self, state, request=None) -> AsyncGenerator[T, None]:
        """子类实现：创建资源 → yield → 清理资源"""
        yield None

    @contextlib.asynccontextmanager
    async def context(self, state, request=None) -> AsyncGenerator[T, None]:
        """上下文管理器用法"""
        async for result in self.inject(state, request):
            yield result

    async def depends(self, request) -> AsyncGenerator[T, None]:
        """FastAPI 依赖注入入口"""
        async for result in self.inject(request.state, request):
            yield result
```

**使用方式**：
```python
# 定义一个数据库 Session 注入器
class DbSessionInjector(Injector[AsyncSession]):
    async def inject(self, state, request=None) -> AsyncGenerator[AsyncSession, None]:
        session = async_session_maker()
        try:
            yield session                          # 给路由用
            await session.commit()                  # 请求结束自动提交
        except Exception:
            await session.rollback()                # 出错自动回滚
        finally:
            await session.close()                   # 自动关闭
```

**Java 对照**：
```java
// Spring 中的等价写法
@Bean
@Scope(value = SCOPE_REQUEST)
public Session dbSession() {
    Session session = sessionFactory.openSession();
    // ... 请求结束自动关闭
    return session;
}
```

---

## 5.2 动态实现替换 — Spring @Conditional 的 Python 版

```python
# 来自 openhands/app_server/utils/import_utils.py
import importlib
from functools import lru_cache

def import_from(qual_name: str):
    """动态导入 — Java: Class.forName()"""
    parts = qual_name.split('.')
    module = importlib.import_module('.'.join(parts[:-1]))   # 加载模块
    return getattr(module, parts[-1])                         # 获取类

@lru_cache()                              # 单例缓存
def get_impl(base_class, impl_name: str | None):
    """根据配置选择实现类 — Spring @Conditional"""
    if impl_name is None:
        return base_class                  # 默认实现
    impl = import_from(impl_name)          # 动态加载
    assert issubclass(impl, base_class)    # 类型安全检查
    return impl

# 使用
# 配置: analytics_user_provider_class = "enterprise.SaasUserProvider"
provider_class = get_impl(AnalyticsUserProvider, config.analytics_user_provider_class)
provider = provider_class()                # 实例化
```

---

## 5.3 Protocol — 不用 implements 的接口

```python
# 来自 openhands/app_server/integrations/service_types.py
from typing import Protocol

class GitService(Protocol):
    """定义接口 — 但不需要类声明 implements"""
    async def get_user(self) -> User: ...
    async def search_repositories(self, ...) -> list[Repository]: ...

# 任何有这些方法的对象都自动满足这个接口（鸭子类型）
class GitHubService:
    async def get_user(self) -> User:       # 不需要写 implements GitService
        ...
    async def search_repositories(self, ...) -> list[Repository]:
        ...

# GitHubService 自动满足 GitService 协议！
```

**和 Java 的区别**：
- Java：`class GitHubService implements GitService` — 必须声明
- Python：只要方法签名匹配，就自动满足 — 不用声明

---

## 5.4 Mixin — 用多重继承组合功能

Java 不支持多重继承，Python 可以，这就是 Mixin 模式：

```python
# 来自 openhands/app_server/integrations/github/service/

# 基类：提供公共方法
class GitHubMixinBase(BaseGitService, HTTPClient):
    async def _get_headers(self) -> dict: ...

# 功能 Mixin 1：仓库操作
class GitHubReposMixin(GitHubMixinBase):
    async def get_installations(self) -> list[str]: ...
    async def get_all_repositories(self, ...) -> list[Repository]: ...

# 功能 Mixin 2：PR 操作
class GitHubPRsMixin(GitHubMixinBase):
    async def get_prs(self, ...) -> list[PR]: ...

# 最终组合
class GitHubService(GitHubReposMixin, GitHubPRsMixin):
    """继承了所有 Mixin 的功能"""
    pass
```

**Java 对照**：需要用接口 + 默认方法，或组合模式（更繁琐）。

---

## 5.5 日志 — 和 SLF4J 几乎一样

```python
# 来自项目全局模式
import logging

logger = logging.getLogger(__name__)       # LoggerFactory.getLogger(getClass())

# 使用
logger.info('Callback %s invoked for event %s', callback_id, event_id)
logger.warning('Rate limit exceeded on %s API', provider)
logger.exception('Failed to process')      # 自动打印异常堆栈
```

| SLF4J | Python logging |
|-------|---------------|
| `logger.info("msg {}", arg)` | `logger.info("msg %s", arg)` |
| `logger.error("msg", e)` | `logger.exception("msg")` |
| `LoggerFactory.getLogger(X.class)` | `logging.getLogger(__name__)` |

---

## 5.6 测试 — pytest 比 JUnit 更简洁

```python
# 来自 tests/unit/app_server/
import pytest
from unittest.mock import AsyncMock, MagicMock

# 异步测试
@pytest.mark.asyncio                            # 标记异步测试
async def test_search_conversations():
    # Mock — 类似 Mockito.when()
    mock_service = AsyncMock()
    mock_service.search.return_value = some_result

    # 调用
    result = await mock_service.search(title="test")

    # 断言 — 比 JUnit 的 assertEquals 更直观
    assert result is not None
    assert len(result.items) > 0
    mock_service.search.assert_called_once()     # verify()
```

---

# 附录 A：速查对照表

| Java | Python | 说明 |
|------|--------|------|
| `String s = "hi"` | `s = "hi"` | 不用声明类型 |
| `Optional<String>` | `str \| None` | 可空类型 |
| `List<String>` | `list[str]` | 列表 |
| `Map<String, String>` | `dict[str, str]` | 字典 |
| `final` | `frozen=True` | 不可变 |
| `interface` | `Protocol` | 接口 |
| `abstract class` | `ABC + @abstractmethod` | 抽象类 |
| `@Data` / `record` | `@dataclass` / `BaseModel` | 数据类 |
| `@Autowired` | FastAPI `Depends` | 依赖注入 |
| `@GetMapping` | `@router.get` | GET 路由 |
| `@PostMapping` | `@router.post` | POST 路由 |
| `@ExceptionHandler` | `@app.exception_handler` | 异常处理 |
| `CompletableFuture` | `async/await` | 异步 |
| `ExecutorService` | `ThreadPoolExecutor` | 线程池 |
| `Class.forName()` | `importlib.import_module()` | 动态加载 |
| `@Singleton` | `@lru_cache()` | 单例缓存 |
| `ObjectMapper` | Pydantic `TypeAdapter` | JSON 序列化 |
| `SLF4J` | `logging` | 日志 |
| `JUnit` | `pytest` | 测试 |
| `Mockito` | `unittest.mock` | Mock |
| `Flyway` | `Alembic` | 数据库迁移 |
| `WebClient` | `httpx.AsyncClient` | HTTP 客户端 |
| `String.format()` | `f"..."` | 字符串模板 |
| `stream().map()` | `[f(x) for x in list]` | 列表推导 |
| `stream().filter()` | `[x for x in list if cond]` | 过滤 |
| `try-with-resources` | `async with` | 资源管理 |
| `throw` | `raise` | 抛异常 |
| `catch` | `except` | 捕获异常 |

---

# 附录 B：Python 独特写法速记

```python
# 1. 列表推导（最常用！）
nums = [1, 2, 3, 4, 5]
doubled = [n * 2 for n in nums]                 # [2, 4, 6, 8, 10]
evens = [n for n in nums if n % 2 == 0]         # [2, 4]

# 2. 字典推导
squares = {n: n**2 for n in range(5)}           # {0:0, 1:1, 2:4, 3:9, 4:16}

# 3. 解包
a, b = 1, 2                                     # 多赋值
first, *rest = [1, 2, 3, 4]                     # first=1, rest=[2,3,4]

# 4. 短路默认值
name = input_name or "Anonymous"                 # 等价于 Java: inputName != null ? inputName : "Anonymous"

# 5. 字典 get 方法（避免 KeyError）
value = d.get('key')                            # 不存在返回 None
value = d.get('key', 'default')                 # 不存在返回 'default'

# 6. collections.defaultdict
from collections import defaultdict
groups = defaultdict(list)                       # 不存在的 key 返回空列表
groups['a'].append(1)                           # 不用先初始化

# 7. 三元表达式
status = "running" if is_active else "stopped"  # Java: isActive ? "running" : "stopped"
```

---

*本手册所有代码实例均来自 OpenHands 项目源码。建议按阶段顺序学习，每阶段完成后在项目中找到对应代码阅读理解。*
