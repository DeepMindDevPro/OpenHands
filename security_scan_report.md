# OpenHands 安全扫描报告：API Key 泄漏风险评估

## 结论：京东云 API Key 不会泄漏到公网

---

## 详细安全评估

### 1. API Key 不会发送到公网/第三方 ✅

- 使用 `openai/pre-qwen35-35B-A3B` + 自定义 `base_url`，LLM 调用通过 litellm 直接发往京东云端点
- 只有 `openhands/` 前缀的模型才会走 OpenHands 的 LLM Proxy（`llm-proxy.app.all-hands.dev`），当前配置不走此路径

### 2. GET 请求不返回 API Key 明文 ✅

`openhands/app_server/settings/settings_router.py:168` 明确将 API Key 置空：

```python
resp_llm.api_key = None  # 返回给前端时清除
```

前端只能看到 `api_key_set: true/false`，拿不到明文。

### 3. API Key 在数据库中加密存储 ✅

- 使用 JWE（JSON Web Encryption）加密后存入 SQLite
- 加密密钥由 `openhands/app_server/utils/encryption_key.py` 管理，存储在 `workspace/.keys` 文件中
- 直接读 SQLite 数据库也拿不到明文

### 4. 日志中 API Key 被脱敏 ✅

`openhands/app_server/utils/logger.py:276-303` 实现了多层脱敏：

- 匹配 `api_key=` 等模式的正则替换为 `******`
- 调用 `redact_api_key_literals()` 清除 `sk_live_` 等常见 Key 前缀
- 调用 `redact_text_secrets()` 清除更多敏感值

### 5. 唯一风险：本地无认证 ⚠️

`openhands/app_server/utils/dependencies.py:23-26` 显示：**本地模式下未设置 `SESSION_API_KEY` 环境变量时，所有 API 端点无认证保护**。这意味着：

- 如果电脑被同网段其他人访问 `http://127.0.0.1:3000`，他们可以操作你的 OpenHands
- 但 API Key 仍然不会通过 GET 接口泄露（见第 2 点）
- POST 保存设置时可以覆盖你的 API Key，但看不到现有值

### 6. config.toml 明文存储 ⚠️

`config.toml` 中的 API Key 是明文，但这是本地文件，只要电脑不被他人访问就安全。

---

## 建议加固措施

1. **启动时设置 SESSION_API_KEY**：

   ```bash
   export SESSION_API_KEY="你自己的随机密码"
   INSTALL_DOCKER=0 RUNTIME=local poetry run uvicorn ...
   ```

   这样所有 API 请求都需要带 `X-Session-API-Key` 头。

2. **不要把 config.toml 提交到 Git**（已在 `.gitignore` 中排除）。

3. **绑定 localhost**（当前默认 `127.0.0.1`，已是安全配置，不要改成 `0.0.0.0`）。
