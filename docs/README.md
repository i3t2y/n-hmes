### **n-hmes 项目权威架构与运维手册**

**本文档是项目的唯一权威参考。任何 AI 接手本项目时，无需其他上下文，仅凭本文档即可理解架构、定位问题、提供修复建议。**

---

### **1. 项目核心定位**
`n-hmes` 是基于 `democra-ai/HermesFace` 深度定制的“清爽版”AI Agent 部署库。它通过 Docker 源码构建方案，在 HuggingFace Spaces 上实现了一个全功能的、具备自进化能力的 Hermes Agent，并解决了原版镜像权限报错、LFS 大文件冗余及数据持久化不稳等痛点。

---

### **2. 架构设计与调用链**

#### **2.1 启动流水线 (Bootstrap Flow)**
1.  **宿主环境**：HuggingFace Space (Debian 13.4)。
2.  **入口点 (PID 1)**：`scripts/entrypoint.sh`。
    *   执行 DNS 预解析（绕过 HF 对 Telegram 等 API 的封锁）。
    *   激活 Python 虚拟环境 (`/opt/hermes/.venv`)。
    *   **关键转向**：将控制权交给 `/opt/data/app.py`。
3.  **调度层 (Wrapper)**：`/opt/data/app.py`。
    *   拉起独立守护线程 `r2_sync_loop`（每小时执行一次异地备份）。
    *   启动主同步逻辑 `scripts/sync_hf.py`。
4.  **业务层 (Core)**：`scripts/sync_hf.py`。
    *   **持久化**：从 HF Dataset 恢复数据到 `/opt/data`。
    *   **安全**：通过环境变量注入 Dashboard 认证（用户名默认 `admin`）。
    *   **启动**：拉起 `hermes dashboard` (Port 7860) 和 `hermes gateway` (聊天机器人)。

#### **2.2 数据持久化策略 (Dual-Sync)**
*   **一级同步 (HF Dataset)**：由 `sync_hf.py` 负责，每 60 秒将 `/opt/data` 全量同步至私有数据集，确保重启后记忆、技能不丢失。
*   **二级同步 (Cloudflare R2)**：由 `app.py` 拉起的线程调用 `sync_to_r2.py` 负责，每小时执行一次，实现数据的跨云异地冗余。

---

### **3. 核心文件清单 (权威源)**

| 路径 | 核心作用 | AI 维护重点 |
| :--- | :--- | :--- |
| `Dockerfile` | 环境定义与依赖安装 | 必须在 `uv pip install` 时预装 `huggingface_hub` 等持久化库。 |
| `app.py` | R2 线程入口与主程序包装 | 内部脚本路径必须使用 `/opt/data/scripts/` 绝对路径。 |
| `scripts/entrypoint.sh` | 容器初始化脚本 | 结尾必须 `exec python3 -u /opt/data/app.py` 确保调用链完整。 |
| `scripts/sync_hf.py` | HF 持久化与 Dashboard 逻辑 | 必须包含 `HERMES_DASHBOARD_BASIC_AUTH` 环境变量注入逻辑。 |
| `scripts/sync_to_r2.py`| R2 上传逻辑 | 依赖 `boto3`，需检查 `R2_*` 系列环境变量。 |
| `.github/workflows/` | 自动化同步脚本 | 使用 `git push --force` 确保 GitHub 是 HF 的唯一权威镜像源。 |

---

### **4. 关键环境变量 (Secrets)**

| 变量名 | 作用 | 备注 |
| :--- | :--- | :--- |
| `HF_TOKEN` | 访问 HF API 的令牌 | 必须具备 **Write** 权限。 |
| `DASHBOARD_PASSWORD` | 网页面板登录密码 | 必填，否则 Dashboard 拒绝启动。 |
| `AUTO_CREATE_DATASET` | 自动创建备份库 | 建议设为 `true`。 |
| `R2_ENDPOINT` 等 | R2 存储配置 | 若需异地备份，需配齐 Endpoint/Key/Bucket。 |
| `CLOUDFLARE_PROXY_URL`| Telegram 代理 | 用于绕过 HF 网络限制，对应 CF Worker 地址。 |

---

### **5. 故障排查 (Troubleshooting)**

*   **Dashboard 无法访问/报错 1**：检查日志是否有 `Refusing to bind dashboard to 0.0.0.0`。
    *   *修复*：确保 `DASHBOARD_PASSWORD` 已设置，且 `sync_hf.py` 包含认证注入逻辑。
*   **ModuleNotFoundError: 'huggingface_hub'**：
    *   *修复*：检查 `Dockerfile`，确保在 `uv venv` 之后执行了 `uv pip install huggingface_hub`。
*   **R2 备份未生效**：
    *   *修复*：检查 `entrypoint.sh` 是否指向了 `app.py`，而非直接指向 `sync_hf.py`。
*   **LFS 404 错误**：
    *   *修复*：项目已彻底剔除 LFS 依赖，严禁在仓库中添加超过 5MB 的二进制文件，严禁恢复 `.gitattributes`。

---

### **6. 运维准则**
1.  **GitHub 优先**：禁止在 HF Space 网页端直接修改代码。所有改动必须在 GitHub 提交，通过 Actions 自动同步。
2.  **绝对路径**：在 `app.py` 和 `entrypoint.sh` 中引用脚本时，优先使用 `/opt/data/scripts/` 前缀。
3.  **清爽原则**：保持根目录简洁，非运行必需的文档一律存放在 `docs/` 目录下。

---

**项目状态：已对齐 nomke/hm 成熟版本，R2 链路已接通，Dashboard 认证已激活。**

*内容由 AI 生成仅供参考*
