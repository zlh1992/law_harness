# 本地法务助手 · DeepSeek Harness

这是一个以 DeepSeek Harness 为界面和编排层的本地法务助手：模型请求经本机 OpenAI 兼容桥接到已登录的 Codex ChatGPT 订阅，并固定使用 `gpt-5.6-sol`。它不需要 OpenAI Platform API Key。

```text
浏览器 / HTTPS 公网入口
  → 口令登录网关 :4180（仅回环监听）
  → DeepSeek Harness :3080
  → 本地 OpenAI 兼容桥 :4010
  → codex exec（ChatGPT 订阅）→ GPT-5.6 Sol

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
- `gateway/public-gateway.mjs`：公网前置登录网关，使用 HMAC 签名、HttpOnly、SameSite=Strict 会话、限速和安全响应头；Harness、代理和 MCP 均不直接暴露。

## 一键启动

前提：Mac 已完成 `codex login` 的 ChatGPT 订阅登录，且有 Node.js 与 Python 3.10+。

```bash
cd /Users/zlh1992_home/Desktop/law_harness
./install/install-mac.sh
./install/install-law-integrations.sh
./install/install-internet-tools.sh
./bin/start-public.sh
```

脚本会启动全部本地服务，并优先使用项目内的 `cloudflared` 创建 `https://…trycloudflare.com` Quick Tunnel；若未安装才回退到 LocalTunnel。首次访问打印出的地址时输入 `.env` 内的 `PUBLIC_ACCESS_PASSWORD`。公网用户只能使用预注册的“法务助手”工作区和会话，不能浏览服务器目录、改设置或改凭据。服务运行期间不要关闭该启动终端；按 `Ctrl-C` 即可关闭隧道和所有子服务。

### 固定公网地址（推荐）

Quick Tunnel 的网址每次启动都会改变。要使用固定域名，在 Cloudflare 控制台创建 remotely-managed named tunnel，并为它添加 Published application：固定域名（例如 `law.example.com`）映射到 `http://localhost:4180`。从隧道的 **Add a replica** 页面复制 token，再用隐藏输入脚本保存，避免秘密进入 Shell 历史或进程参数：

```bash
cd /Users/zlh1992_home/Desktop/law_harness
./bin/save-cloudflare-tunnel-token.sh
```

然后在 `.env` 增加或修改：

```dotenv
PUBLIC_TUNNEL_MODE=named
PUBLIC_URL=https://law.example.com
PUBLIC_TUNNEL_TOKEN_FILE=.data/cloudflare-tunnel.token
```

再次运行 `./bin/start-public.sh`，以后打印的就是同一个 `PUBLIC_URL`。该方案是出站隧道，不需要在路由器或 macOS 防火墙开放入站端口；固定域名仍先到项目的口令网关，只有 `4180` 的本机回环地址会被隧道映射，Harness `3080` 和模型桥 `4010` 不会直接暴露。token 文件位于已忽略的 `.data/`，不要把 token 写入 Git、聊天或命令行参数；怀疑泄露时应在 Cloudflare 旋转 token。

没有自有域名时，可安装并登录 Tailscale，然后在 `.env` 设置 `PUBLIC_TUNNEL_MODE=tailscale`。启动脚本会使用 Funnel 将固定的 `https://<设备名>.<tailnet>.ts.net` 映射到 `http://127.0.0.1:4180`。Funnel 仍受项目口令网关保护；地址固定，但本机和启动脚本必须保持运行。

仅本机使用则分别启动：

```bash
npm run start:proxy
npm run start:harness -- "$PWD"
```

访问 [http://127.0.0.1:3080](http://127.0.0.1:3080)。公网网关的本机登录页是 [http://127.0.0.1:4180/login](http://127.0.0.1:4180/login)。

## 配置与验证

- `.env` 中的 `LAW_PROXY_TOKEN` 会在启动时映射为 Harness 所需的受保护变量；不要把受保护变量 `DSH_PROXY_TOKEN` 直接写入 `.env`。
- `PUBLIC_ACCESS_PASSWORD` 必须不同于代理口令；`PUBLIC_WORKSPACE_ID` 锁定允许公网创建会话的“法务助手”工作区，阻止公网请求切换到标准 Agent 或任意主机目录。`.env` 权限应保持为 `600`，且所有本地状态已由 `.gitignore` 忽略。
- 固定地址可使用 `PUBLIC_TUNNEL_MODE=named`（自有域名）或 `tailscale`（免费 `*.ts.net` 地址）；默认 `quick` 模式继续提供临时演示网址。
- 公网文档默认限制为单文件 25 MB、每会话 250 MB，可通过 `PUBLIC_UPLOAD_MAX_BYTES` 与 `PUBLIC_UPLOAD_SESSION_MAX_BYTES` 调整。公网不能登记本机路径；文件以 `0600` 权限按 Session 隔离保存。
- `npm test`：验证 OpenAI 兼容桥、认证、SSE、Responses 和 tool calls。
- 在 Harness 中调用 `mcp__law_wiki__okf_status` 或 `mcp__law_wiki__okf_validate`：检查当前 OKF 包版本与合规状态；运行时默认知识根目录为 `knowledge/legal_okf/`。
- `npm run install:internet`：下载并校验固定版本的 Agent Reach 与 Free Search 源码，在本机 `.tools/upstreams/` 建立隔离运行时（首次需要联网和 Chromium 下载）。
- `npm run health`：验证本地代理。

## 安全与法务边界

公网入口适合短期、受控演示或授权用户使用；它仍会把提问发送至 Codex ChatGPT 订阅后端以获得 GPT-5.6 Sol 回答。因此不要提交身份证号、完整合同、商业秘密、未脱敏个人信息或尚未获准外发的案件材料。输出是法务风险分流和工作底稿，不是正式法律意见；法定期限、对外文件和最终结论必须由执业律师确认。

DS4 本地推理模式仍保留在 `ds4/` 与 `config/dsh-settings-ds4.yaml`，与当前 GPT-5.6 Sol 桥接模式分开配置。更多细节见 [启动与安装](docs/启动与安装.md)、[客户演示脚本](docs/客户演示脚本.md) 与 [项目边界](docs/项目边界.md)。
