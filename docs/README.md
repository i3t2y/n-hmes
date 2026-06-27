### **n-hmes 项目权威架构与运维手册**

**本文档是项目的唯一权威参考。任何 AI 接手本项目时，无需其他上下文，仅凭本文档即可理解架构、定位问题、提供修复建议。**

---

### **1. 项目核心定位**
`n-hmes` 是基于 `democra-ai/HermesFace` 深度定制的"清爽版"AI Agent 部署库。它通过 Docker 源码构建方案，在 HuggingFace Spaces 上实现了一个全功能的、具备自进化能力的 Hermes Agent，并解决了原版镜像权限报错、LFS 大文件冗余及数据持久化不稳等痛点。

---

### **2. 架构设计与调用链**

#### **2.1 启动流水线 (Bootstrap Flow)**
1. **宿主环境**：HuggingFace Space (Debian 13.4)。
2. **入口点 (PID 1)**：`scripts/entrypoint.sh`。
   - 执行 DNS 预解析（绕过 HF 对 Telegram 等 API 的封锁）。
   - 激活 Python 虚拟环境 (`/opt/hermes/.venv`)。
   - **关键转向**：将控制权交给 `/opt/data/app.py`。
3. **调度层 (Wrapper)**：`/opt/data/app.py`。
   - 拉起独立守护线程 `r2_sync_loop`（每小时执行一次异地备份）。
   - 启动主同步逻辑 `scripts/sync_hf.py`。
4. **业务层 (Core)**：`scripts/sync_hf.py`。
   - **持久化**：从 HF Dataset 恢复数据到 `/opt/data`。
   - **代理注入**：读取 `CLOUDFLARE_PROXY_URL`，强制覆写 `config.yaml` 中的 `platforms.telegram.extra.base_url`（每次启动都执行，不可跳过）。
   - **安全**：通过环境变量注入 Dashboard 认证（用户名默认 `admin`）。
   - **启动**：拉起 `hermes dashboard` (Port 7860) 和 `hermes gateway`（聊天机器人）。

#### **2.2 数据持久化策略 (Dual-Sync)**
- **一级同步 (HF Dataset)**：由 `sync_hf.py` 负责，每 3600 秒将 `/opt/data` 全量同步至私有数据集，确保重启后记忆、技能不丢失。
- **二级同步 (Cloudflare R2)**：由 `app.py` 拉起的线程调用 `sync_to_r2.py` 负责，每小时执行一次，实现数据的跨云异地冗余。

#### **2.3 Telegram 代理架构 (TeleBridge)**
HuggingFace Spaces 在网络层封锁了 `api.telegram.org` 的 DNS 解析，同时也封锁了 `*.workers.dev` 域名，因此必须通过部署在 Vercel 上的 TeleBridge 反向代理转发所有 Telegram API 请求。

```
Hermes Gateway
    │
    ▼
TeleBridge (Vercel)
https://tele-bridge-seven.vercel.app
    │  路由: /bot/{token}/{method}
    ▼
api.telegram.org
    │
    ▼
Telegram 用户
```

**TeleBridge 关键特性：**
- 仓库：`expher510/TeleBridge`（需 fork 到自己账户部署）
- 路由正则必须兼容两种格式：`/bot{token}/method` 和 `/bot/{token}/method`
- 依赖 Upstash Redis 存储 webhook URL 映射（`KV_REST_API_URL` + `KV_REST_API_TOKEN`）
- 生产域名：`tele-bridge-seven.vercel.app`（非预览域名 `tele-bridge-*-nomke.vercel.app`）

**`sync_hf.py` 代理注入逻辑（必须保持此格式）：**
```python
tg["extra"] = {
    "base_url": f"{_proxy}/bot",
    "base_file_url": f"{_proxy}/file/bot",
}
```
`python-telegram-bot` v20+ 的拼接规则是 `base_url + "/" + token + "/" + method`，因此 `base_url` 必须以 `/bot` 结尾（不加末尾斜杠）。

---

### **3. 核心文件清单 (权威源)**

| 路径 | 核心作用 | AI 维护重点 |
| :--- | :--- | :--- |
| `Dockerfile` | 环境定义与依赖安装 | Node.js 版本必须为 **v22**（v20 与 `node-pty` 编译不兼容）；必须在 `uv pip install` 时预装 `huggingface_hub` 等持久化库。 |
| `app.py` | R2 线程入口与主程序包装 | 内部脚本路径必须使用 `/opt/data/scripts/` 绝对路径。 |
| `scripts/entrypoint.sh` | 容器初始化脚本 | 结尾必须 `exec python3 -u /opt/data/app.py` 确保调用链完整。 |
| `scripts/sync_hf.py` | HF 持久化、代理注入与 Dashboard 逻辑 | 必须包含 `HERMES_DASHBOARD_BASIC_AUTH` 注入逻辑；`base_url` 必须以 `/bot` 结尾；此文件内置于镜像，不来自 dataset 同步。 |
| `scripts/sync_to_r2.py` | R2 上传逻辑 | 依赖 `boto3`，需检查 `R2_*` 系列环境变量。 |
| `.github/workflows/` | 自动化同步脚本 | 使用 `git push --force` 确保 GitHub 是 HF 的唯一权威镜像源。 |

---

### **4. 关键环境变量 (Secrets)**

| 变量名 | 作用 | 备注 |
| :--- | :--- | :--- |
| `HF_TOKEN` | 访问 HF API 的令牌 | 必须具备 **Write** 权限。 |
| `TELEGRAM_BOT_TOKEN` | Telegram Bot 令牌 | 格式为 `数字:字母串`，从 @BotFather 获取。 |
| `TELEGRAM_ALLOWED_USERS` | Telegram 白名单用户 | 填写允许与 Bot 交互的 Telegram 用户 ID，逗号分隔。 |
| `CLOUDFLARE_PROXY_URL` | Telegram 反向代理地址 | 填 TeleBridge 的 Vercel **生产域名**，不带末尾斜杠，不带 `/bot`。当前值：`https://n-hmes.vercel.app`。 |
| `HERMES_TELEGRAM_BASE_URL` | Telegram base_url 备用覆盖 | 部分版本 Hermes 支持此变量直接覆盖 base_url，与 `CLOUDFLARE_PROXY_URL` 二选一，优先用后者。 |
| `DASHBOARD_PASSWORD` | 网页面板登录密码 | 必填，否则 Dashboard 拒绝绑定 `0.0.0.0` 并退出。 |
| `GATEWAY_TOKEN` | Gateway 鉴权 Token | 与 `DASHBOARD_PASSWORD` 二选一，两者均设时 `DASHBOARD_PASSWORD` 优先。 |
| `AGENT_NAME` | Agent 显示名称 | 默认值 `HermesFace`，可自定义。 |
| `OPENROUTER_API_KEY` | OpenRouter 模型调用密钥 | 用于接入 OpenRouter 上的各类模型。 |
| `OPENAI_API_KEY` | OpenAI 模型调用密钥 | 用于接入 OpenAI 系列模型。 |
| `AUTO_CREATE_DATASET` | 自动创建 HF 备份数据集 | 建议设为 `true`，首次启动时自动创建私有 dataset。 |
| `SYNC_INTERVAL` | HF Dataset 同步间隔（秒） | 默认 `60`，当前已调整为 `3600`，减少 API 调用频率。 |
| `TZ` | 时区设置 | 影响日志时间戳显示，如 `Asia/Shanghai`。 |
| `R2_ENDPOINT` | Cloudflare R2 存储端点 | 格式：`https://<账户ID>.r2.cloudflarestorage.com`。 |
| `R2_ACCESS_KEY` | R2 访问密钥 ID | 从 Cloudflare Dashboard 创建 R2 API Token 获取。 |
| `R2_SECRET_KEY` | R2 访问密钥 Secret | 同上，创建时仅显示一次，需妥善保存。 |
| `R2_BUCKET_NAME` | R2 存储桶名称 | 对应 Cloudflare R2 中创建的 Bucket 名。 |
| `R2_MAX_FILES` | R2 备份文件数量上限 | 超出上限时中止同步，防止意外上传过多文件。当前触发阈值为 500。 |
---

### **5. TeleBridge 运维 (独立组件)**

TeleBridge 是独立部署在 Vercel 的 Node.js 项目，需单独维护。

| 变量名 | 填写位置 | 作用 |
| :--- | :--- | :--- |
| `KV_REST_API_URL` | Vercel 环境变量 | Upstash Redis REST 地址 |
| `KV_REST_API_TOKEN` | Vercel 环境变量 | Upstash Redis REST Token |

**注意事项：**
- Vercel 对 GET 请求有边缘缓存，可能返回 304 导致 `python-telegram-bot` 报错。`handler.js` 中必须设置 `Cache-Control: no-store`。
- 路由正则必须为 `/^\/bot\/?([^/]+)\/(.+)$/`，兼容带斜杠和不带斜杠两种格式。
- 修改 `handler.js` 后 Vercel 自动重新部署，无需手动触发，但需等待部署完成后再 Restart HF Space。

---

### **6. 故障排查 (Troubleshooting)**

**Dashboard 无法访问**：检查日志是否有 `Refusing to bind dashboard to 0.0.0.0`。
- *修复*：确保 `DASHBOARD_PASSWORD` 已设置，且 `sync_hf.py` 包含认证注入逻辑。

**`ModuleNotFoundError: 'huggingface_hub'`**：
- *修复*：检查 `Dockerfile`，确保在 `uv venv` 之后执行了 `uv pip install huggingface_hub`。

**`node-pty` 编译失败（`gyp ERR`）**：
- *修复*：Dockerfile 中 Node.js 版本必须为 v22，v20 与 `node-pty 1.1.0` 不兼容。若为 `undici` AssertionError，属于网络偶发错误，重新触发构建即可。

**`InvalidURL("Invalid port: 'AAH...'")`**：
- *原因*：`base_url` 格式错误，Token 被解析为端口号。
- *修复*：确认 `CLOUDFLARE_PROXY_URL` 不含 Token，`sync_hf.py` 中 `base_url` 为 `f"{_proxy}/bot"`。

**Telegram 连接 302 Redirecting**：
- *原因1*：TeleBridge 路由正则不兼容，`/bot/{token}/method` 未被匹配。修复：正则改为 `/^\/bot\/?([^/]+)\/(.+)$/`。
- *原因2*：`CLOUDFLARE_PROXY_URL` 填写的是预览域名而非生产域名。修复：改为 `tele-bridge-seven.vercel.app`。
- *原因3*：`http://` 而非 `https://`，Vercel 强制跳转。修复：改为 `https://`。

**Telegram 连接超时**：
- *原因*：TeleBridge Upstash Redis 未配置，或使用了公共实例（`tele-bridge-seven.vercel.app` 是原作者实例，随时可能失效）。
- *修复*：fork `expher510/TeleBridge` 部署自己的实例，配置 Upstash Redis 环境变量。

**R2 备份未生效**：
- *修复*：检查 `entrypoint.sh` 是否指向了 `app.py`，而非直接指向 `sync_hf.py`。

**LFS 404 错误**：
- *修复*：项目已彻底剔除 LFS 依赖，严禁在仓库中添加超过 5MB 的二进制文件，严禁恢复 `.gitattributes`。

**`sync_hf.py` 修改不生效**：
- *原因*：`sync_hf.py` 内置于 Docker 镜像，不来自 dataset 同步，修改必须提交到 Space 源码仓库并触发镜像重建（Factory rebuild）。
- *注意*：dataset 里的 `config.yaml` 会被 `sync_hf.py` 每次启动强制覆写，不要依赖手动编辑 dataset 里的 `config.yaml` 来修改代理配置，应通过 `CLOUDFLARE_PROXY_URL` Secret 控制。

---

### **7. 运维准则**
1. **GitHub 优先**：禁止在 HF Space 网页端直接修改代码。所有改动必须在 GitHub 提交，通过 Actions 自动同步。
2. **绝对路径**：在 `app.py` 和 `entrypoint.sh` 中引用脚本时，优先使用 `/opt/data/scripts/` 前缀。
3. **清爽原则**：保持根目录简洁，非运行必需的文档一律存放在 `docs/` 目录下。
4. **两次重启原则**：修改 `sync_hf.py` 后需 Factory rebuild 而非 Restart，因为该文件内置于镜像中。
5. **域名区分**：Vercel 生产域名（`tele-bridge-seven.vercel.app`）与预览域名（带随机串的 `tele-bridge-*-nomke.vercel.app`）行为可能不一致，`CLOUDFLARE_PROXY_URL` 必须填生产域名。

---

**项目状态：Telegram 通道已通过 TeleBridge 打通，Dashboard 认证已激活，R2 链路已接通，HF Dataset 持久化正常。**
