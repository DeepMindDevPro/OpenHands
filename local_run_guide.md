# OpenHands 本地运行指南（无 Docker）

## 环境状态

| 项目 | 状态 |
|------|------|
| Python 3.12.13 (openhands conda) | ✅ |
| Poetry 2.4.1 | ✅ |
| Node.js v22.22.2 / npm 10.9.7 | ✅ |
| Python 依赖 (poetry 虚拟环境) | ✅ 已安装 |
| 前端依赖 (node_modules) | ✅ 已安装 |
| 前端构建 (frontend/build) | ✅ 已完成 |
| Docker | ❌ 不需要 |

---

## 第 1 步：配置 LLM

`config.toml` 内容如下：

```toml
[core]
workspace_base = "./workspace"
runtime = "local"

[llm]
model = "openai/pre-qwen35-35B-A3B"
api_key = ""
base_url = ""
```

关键说明：
- `runtime = "local"` 使用 **ProcessSandbox**，直接在本地启动子进程执行命令，无需 Docker
- `model = "openai/pre-qwen35-35B-A3B"` 中的 `openai/` 前缀告诉 litellm 使用 OpenAI 兼容协议
- `base_url` 是京东云大模型的 API 端点（兼容 OpenAI 协议）

---

## 第 2 步：启动后端

### 基础启动命令

```bash
conda activate openhands
cd /Users/gechunfa1/Documents/ai-code/OpenHands

mkdir -p workspace  # 确保工作目录存在

INSTALL_DOCKER=0 RUNTIME=local poetry run uvicorn openhands.server.listen:app \
  --host 127.0.0.1 --port 3000 --reload --reload-exclude "./workspace"
```

- `INSTALL_DOCKER=0` 跳过 Docker 检查
- `RUNTIME=local` 使用进程沙箱替代 Docker 容器

### 启用文件日志

默认情况下（非 DEBUG 模式），日志仅输出到终端。要启用文件日志，可在启动命令中添加以下环境变量之一：

#### 方式 1：使用 DEBUG=true（推荐）
```bash
conda activate openhands
cd /Users/gechunfa1/Documents/ai-code/OpenHands

mkdir -p workspace

DEBUG=true INSTALL_DOCKER=0 RUNTIME=local poetry run uvicorn openhands.server.listen:app \
  --host 127.0.0.1 --port 3000 --reload --reload-exclude "./workspace"
```

#### 方式 2：使用 LOG_TO_FILE=true
```bash
conda activate openhands
cd /Users/gechunfa1/Documents/ai-code/OpenHands

mkdir -p workspace

LOG_TO_FILE=true INSTALL_DOCKER=0 RUNTIME=local poetry run uvicorn openhands.server.listen:app \
  --host 127.0.0.1 --port 3000 --reload --reload-exclude "./workspace"
```

#### 方式 3：组合多个环境变量
```bash
conda activate openhands
cd /Users/gechunfa1/Documents/ai-code/OpenHands

mkdir -p workspace

DEBUG=true LOG_TO_FILE=true INSTALL_DOCKER=0 RUNTIME=local poetry run uvicorn openhands.server.listen:app \
  --host 127.0.0.1 --port 3000 --reload --reload-exclude "./workspace"
```

### 日志输出位置

启用文件日志后，日志文件将保存在：
```
/Users/gechunfa1/Documents/ai-code/OpenHands/logs/openhands.log
```

查看实时日志：
```bash
tail -f /Users/gechunfa1/Documents/ai-code/OpenHands/logs/openhands.log
```

> **说明**：
> - `DEBUG=true`：自动将 `LOG_LEVEL` 设为 `DEBUG`，输出更详细的日志
> - `LOG_TO_FILE=true`：将日志写入文件（默认 `LOG_TO_FILE` 值取决于 `LOG_LEVEL == 'DEBUG'`）
> - `LOG_LEVEL`：可自定义，如 `LOG_LEVEL=DEBUG` 或 `LOG_LEVEL=INFO`

> **已修复的 Bug**：原版 `process_sandbox_spec_service.py` 中 `working_dir=''`（空字符串），导致 agent 工具报错 `working_dir '' is not a valid directory`。已修改为 `os.path.join(os.getcwd(), 'workspace')`，确保工作目录指向项目下的 `workspace/` 目录。

后端启动后，直接在浏览器访问：

**http://127.0.0.1:3000**

后端已经内嵌了前端静态文件（在 `frontend/build/` 中），无需单独启动前端开发服务器即可使用。

---

## 可选：单独启动前端开发服务器（热更新）

如果需要修改前端代码并实时预览，可以在另一个终端运行：

```bash
conda activate openhands
cd /Users/gechunfa1/Documents/ai-code/OpenHands

cd frontend && \
VITE_BACKEND_HOST=127.0.0.1:3000 \
VITE_FRONTEND_PORT=3001 \
npm run dev -- --port 3001 --host 127.0.0.1
```

然后访问 **http://127.0.0.1:3001**

---

## SQLite 数据库说明

### 数据库文件位置

| 文件 | 路径 | 说明 |
|------|------|------|
| SQLite 数据库 | `~/.openhands/openhands.db` | 存储会话元数据、事件回调等 |
| 加密密钥 | `~/.openhands/.keys` | JWE 加密主密钥（自动生成） |
| 设置文件 | `~/.openhands/settings.json` | UI 中保存的设置（首次通过 UI 保存后创建） |

可通过环境变量 `OH_PERSISTENCE_DIR` 自定义存储目录，默认为 `~/.openhands`。

### 数据库中存了什么

- **openhands.db** 中存储的是会话元数据（conversation_metadata），包含：会话 ID、标题、LLM 模型名称、token 用量等
- **openhands.db 中不存储 API Key** — API Key 不在数据库表中

### API Key 的存储方式

API Key 有两个存储位置：

1. **config.toml**（明文）：启动时读取的初始配置，仅在本机
2. **settings.json**（明文）：通过 UI Settings 保存后持久化，存储在 `~/.openhands/settings.json`

⚠️ **settings.json 中 API Key 是明文存储**（Pydantic 的 `SecretStr` 在序列化到文件时使用 `expose_secrets=True`），但文件仅在本机 `~/.openhands/` 目录下，只要本机不被他人访问就是安全的。

### 安全评估

| 安全项 | 状态 | 说明 |
|--------|------|------|
| API Key 不发送到公网 | ✅ | LLM 调用直接发往京东云 base_url，不走第三方代理 |
| GET 请求不返回 API Key | ✅ | 后端返回设置时将 api_key 置为 None，仅返回 api_key_set 标志 |
| 日志中 API Key 被脱敏 | ✅ | 多层正则 + redact_api_key_literals 脱敏 |
| 本地无认证保护 | ⚠️ | 未设置 SESSION_API_KEY 时，API 端点无认证 |
| settings.json 明文存储 | ⚠️ | API Key 明文存在本地文件，依赖文件系统权限保护 |

### 加固建议

启动时设置 `SESSION_API_KEY` 环境变量，为 API 端点添加认证：

```bash
export SESSION_API_KEY="你自己的随机密码"
INSTALL_DOCKER=0 RUNTIME=local poetry run uvicorn openhands.server.listen:app \
  --host 127.0.0.1 --port 3000 --reload --reload-exclude "./workspace"
```

---

## 注意事项

1. **LLM 已配置**：京东云千问模型已通过 API 预配置，设置持久化到 `~/.openhands/settings.json`。无需在 UI 中再次手动配置
2. **security_analyzer 已禁用**：京东云千问模型不支持在工具调用中输出 `security_risk` 字段，已将 `security_analyzer` 从 `llm` 改为 `None`（禁用），否则会报错 `Failed to provide security_risk field in tool 'terminal'`
3. **流式输出已开启**：`stream = true` 已配置，LLM 响应会逐 token 流式返回到前端，无需等待完整响应
2. **京东云 LLM 兼容性**：京东云使用 OpenAI 兼容协议，通过 `openai/` 前缀 + 自定义 `base_url` 即可集成
3. **Process Sandbox**：`RUNTIME=local` 模式下，agent 执行的命令直接在你本机运行，注意安全风险
4. **不要绑定 0.0.0.0**：保持默认 `127.0.0.1`，避免暴露到局域网
5. **不要将 config.toml 和 ~/.openhands/ 提交到 Git**
