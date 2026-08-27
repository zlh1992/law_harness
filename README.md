# 本地法务助手 · DeepSeek Harness

这是一个以 DeepSeek Harness 为界面和编排层的本地法务助手。Harness 使用 OpenAI Chat Completions 格式直连本机 DS4F，只使用 `deepseek-v4-flash`。

```text
浏览器 http://127.0.0.1:3080
  → DeepSeek Harness :3080
  → http://127.0.0.1:8000/v1/chat/completions
  → deepseek-v4-flash（Apple Metal）

Harness 同时装配：.dsh/skills、只读法务 LLM Wiki MCP、本地 SQLite Memory MCP、Semantica 溯源 MCP、会话文件插件，以及本机运行的混合互联网检索、Free Search 正文阅读和 Agent Reach 公共平台适配器
```

## 已集成内容

- `knowledge/legal_okf/`：运行时使用的 Google OKF v0.2 法务知识包；含 14 个带稳定概念 ID、来源、信任信号与法域边界的只读概念。`knowledge/law_knowledge_skills/` 保留为原始迁移档案与七份苍颉技能草案。
- `.dsh/skills/`：将七份草案变为 Harness 可发现的项目级技能，另有 `law-wiki-source-index` 入口技能（共 8 个）。
- `dsh/presets/law-assistant/`：法务中文预设；要求风险分流、来源核验、律师复核提示，并仅在用户明确要求时使用记忆。
- `services/local_memory_mcp.py`：内置本地 SQLite MCP（记住、回忆、列出、遗忘），数据保存在 `.data/memory/memory.db`，不上传和不自动记录对话。
- `services/law_wiki_mcp.py`：只读 OKF MCP。保留 `search` / `read_page` / `catalog` 兼容接口，并提供 `okf_search`、概念读取、校验、资源和审计上下文；不会读取知识根目录之外的文件。
- `plugins/law-wiki-graph/`：会话内的 OKF 概念图。支持检索、类型/信任信号筛选、来源关系、会话读取高亮、局部聚焦与节点详情，不写入知识库或会话历史。
- `services/semantica_law_mcp.py`：将回答、关键事实、来源与决策写入 Semantica 图和 PROV 校验记录；追踪数据在 `.data/semantica/`。法务预设要求实质性答复先调用该工具并返回 trace ID。
- `plugins/session-files/`：DeepSeek Harness Host/Client 双端插件。本地界面只登记本机绝对路径；公网界面把文档复制到 `workspaces/session-files/<sessionId>/`。Agent 只能用 `session_file_list` / `session_file_read` 读取当前会话已登记文件，不能浏览任意 Mac 目录。
- `services/internet_research_mcp.py`：统一联网发现入口。每个查询按 Free Search 50% / Tavily 30% / Exa 10% / SerpAPI 10% 单路路由；任一路失败先由 Tavily 兜底，Tavily 失败后再由 Free Search 兜底，最多三次。
- `services/free_search_mcp.py` 与 `services/agent_reach_mcp.py`：只读、受限的本地 MCP 适配器。前者只能读取已知公共 URL/缓存，后者仅支持匿名公开网页、YouTube、Bilibili、V2EX 与 RSS；不会暴露通用 Shell、Cookie、账号、下载或写入能力。
- `gateway/public-gateway.mjs`：保留的受限访问网关实现；当前公网启动入口已禁用，Harness 与 DS4F 都只监听回环地址。

## 一键启动

前提：本机 DS4F 已在 `127.0.0.1:8000` 就绪，并已安装 Node.js 与 Python 3.10+。

```bash
cd /Users/zlh1992_home/Desktop/law_harness
./install/install-mac.sh
./install/install-law-integrations.sh
./install/install-internet-tools.sh
./bin/start-all.sh "$PWD"
```

访问 [http://127.0.0.1:3080](http://127.0.0.1:3080)。`bin/start-public.sh` 已禁用，不会创建公网隧道。

## 配置与验证

- `.env` 中的 `DS4_API_KEY=local` 只是 OpenAI 兼容客户端占位值，本地服务不要求真实密钥。
- `config/dsh-settings.yaml` 将 Harness 的 `deepseek` provider 覆盖为本机 DS4F，并固定 `deepseek-v4-flash`；上下文 393,216，默认最大输出 8,192，默认正常高强度推理，可在模型选择中切到精确值 `max`。
- 公网文档默认限制为单文件 25 MB、每会话 250 MB，可通过 `PUBLIC_UPLOAD_MAX_BYTES` 与 `PUBLIC_UPLOAD_SESSION_MAX_BYTES` 调整。公网不能登记本机路径；文件以 `0600` 权限按 Session 隔离保存。
- `npm test`：验证网关、法务 Wiki、会话文件和本地 MCP。
- 在 Harness 中调用 `mcp__law_wiki__okf_status` 或 `mcp__law_wiki__okf_validate`：检查当前 OKF 包版本与合规状态；运行时默认知识根目录为 `knowledge/legal_okf/`。
- `npm run install:internet`：下载并校验固定版本的 Agent Reach 与 Free Search 源码，在本机 `.tools/upstreams/` 建立隔离运行时（首次需要联网和 Chromium 下载）。
- `npm run health`：验证 Harness 与本机 DS4F 模型目录连通性。

## 安全与法务边界

模型提示、对话与工具结果只发送到本机 DS4F，不经过云端模型服务。仍不要在未授权工作区处理高敏感材料；输出是法务风险分流和工作底稿，不是正式法律意见，法定期限、对外文件和最终结论必须由执业律师确认。更多细节见 [启动与安装](docs/启动与安装.md)、[客户演示脚本](docs/客户演示脚本.md) 与 [项目边界](docs/项目边界.md)。
